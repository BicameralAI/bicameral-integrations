# SPDX-License-Identifier: MIT
"""Tests for the Live emission seam: AdapterEmission -> v2 ExternalIngestEnvelope + GatewaySink (#226).

The vendored schema ``runtime/schemas/external_ingest_request_v2.schema.json`` is a byte-exact copy
of ``bicameral-bot:protocol/schemas/v2/external-ingest-request.schema.json`` pinned at schema commit
``5c24c60fcba8ed9d04ab5dd6fd0977dcddd9bd57`` (bot HEAD ``22806ac21125b497370786f2ad400b8ba44365cf``;
pin metadata in ``runtime/schemas/ingest_schema_pin.json``). The forbidden-authority list mirrors
``bicameral-bot:crates/bicameral-gateway/src/routes.rs:500-521`` (18 names; 403 at the top level).
The #196 provenance + #198 field-classification disciplines are carried into the v2 envelope as
``candidate_hints[].labels`` and re-asserted here in full.
"""

from __future__ import annotations

import http.server
import io
import json
import threading
import urllib.error
from pathlib import Path

import pytest

from adapter.core.emissions import (
    AdapterEmission,
    AdvisoryResult,
    ConfidenceSurface,
    ProviderProvenance,
    RoutingHint,
    SourceEvidence,
    SourceRef,
)
from adapter.core.pipeline import EmissionContractError
from runtime import (
    GatewayEmissionError,
    GatewayEmissionGated,
    GatewayProtocolMismatch,
    GatewayRedactionGated,
    GatewaySink,
    emission_to_external_envelope,
)
from runtime.gateway_mapping import BOT_OWNED_FIELDS
from runtime.ingest_protocol import (
    EXTERNAL_INGEST_CONTRACT_FINGERPRINT,
    EXTERNAL_INGEST_CONTRACT_ID,
    EXTERNAL_INGEST_REQUEST_SCHEMA_SHA256,
)

_SCHEMA = json.loads(
    (Path(__file__).resolve().parents[1] / "schemas" / "external_ingest_request_v2.schema.json").read_text(
        encoding="utf-8"
    )
)
_TOKEN = "super-secret-operator-token"

# bicameral-bot routes.rs:500-521 — FORBIDDEN_EXTERNAL_FIELDS (authority-injection 403 set)
_FORBIDDEN_EXTERNAL_FIELDS = frozenset({
    "authority", "auth_method", "actor_id", "session_id", "policy_scope",
    "review_command", "tool_command", "approve_signoff", "reject_signoff",
    "resolve_compliance", "compliance_verdict", "policy_grant", "governance_override",
    "canonical_decision", "signoff_state", "decision_id", "compliance_state", "tracking_state",
})


def _emission(**kw) -> AdapterEmission:
    ev = SourceEvidence(
        source_ref=SourceRef(
            source_id="jira", ref="ENG-1", url="https://example.atlassian.net/browse/ENG-1"
        ),
        excerpt="Decided to adopt OAuth.",
    )
    defaults: dict = dict(
        source_id="jira",
        title="Adopt OAuth",
        body="The team decided to adopt OAuth.",
        evidence=(ev,),
        adapter_version="runtime/0.1.0",
    )
    defaults.update(kw)
    return AdapterEmission(**defaults)


def _labels(payload: dict) -> list[str]:
    return payload["candidate_hints"][0].get("labels", [])


def _assert_conforms(payload: dict, *, wire: bool = False) -> None:
    """Emitter-side strict conformance against the vendored v2 schema. NOTE: the gateway itself
    IGNORES unknown non-forbidden top-level keys (the schema carries no additionalProperties
    guard) — the key-set restriction here is the EMITTER's own discipline, locked so an
    accidental extra field can never drift toward the 403'd authority set."""
    assert set(payload) <= set(_SCHEMA["properties"]), "extra top-level key vs emitter discipline"
    for key in _SCHEMA["required"]:
        if key == "redaction_receipt" and not wire:
            continue
        if key == "redaction_receipt":
            assert isinstance(payload.get(key), dict)
            continue
        assert key in payload and isinstance(payload[key], str) and payload[key]
    # gateway 422s only when evidence AND candidate_hints are BOTH empty (routes.rs:716);
    # the emitter guarantees non-empty evidence regardless (boundary invariant, LD2).
    assert isinstance(payload["evidence"], list) and payload["evidence"]
    ev_required = _SCHEMA["definitions"]["ExternalEvidenceItem"]["required"]  # excerpt
    ev_props = set(_SCHEMA["definitions"]["ExternalEvidenceItem"]["properties"])
    for item in payload["evidence"]:
        assert set(item) <= ev_props
        for k in ev_required:
            assert k in item and isinstance(item[k], str) and item[k]  # non-empty excerpt
    hint_required = set(_SCHEMA["definitions"]["ExternalCandidateHint"]["required"])  # body, title
    hint_props = set(_SCHEMA["definitions"]["ExternalCandidateHint"]["properties"])
    for hint in payload.get("candidate_hints", []):
        assert set(hint) <= hint_props
        for k in hint_required:
            assert k in hint and isinstance(hint[k], str) and hint[k]


# --- mapping: source facts ---


def test_mapping_conforms_to_vendored_v2_schema():
    payload = emission_to_external_envelope(_emission())
    _assert_conforms(payload)
    assert payload["source_system"] == "jira"
    assert payload["source_uri"] == "https://example.atlassian.net/browse/ENG-1"
    assert payload["content"] == "The team decided to adopt OAuth."
    assert payload["evidence"] == [{"excerpt": "Decided to adopt OAuth."}]
    hint = payload["candidate_hints"][0]
    assert hint["title"] == "Adopt OAuth" and hint["body"] == payload["content"]


def test_no_forbidden_authority_field_emitted():
    # routes.rs authority-injection 403 set: the emitter must be disjoint BY CONSTRUCTION.
    payload = emission_to_external_envelope(_emission())
    assert not (set(payload) & _FORBIDDEN_EXTERNAL_FIELDS)


def test_required_fields_are_floored():
    ev = SourceEvidence(
        source_ref=SourceRef(source_id="jira", ref="ENG-9", url=""), excerpt="Fallback excerpt."
    )
    e = AdapterEmission(source_id="jira", title="   ", body="", evidence=(ev,), adapter_version="x")
    payload = emission_to_external_envelope(e)
    _assert_conforms(payload)
    assert payload["content"] == "Fallback excerpt."
    assert payload["source_uri"] == "jira:ENG-9"  # no url -> source_id:ref
    assert payload["candidate_hints"][0]["title"] == "Fallback excerpt."


def test_dimensional_confidence_not_collapsed_to_scalar():
    # SG-2026-06-02-B: dimensional ConfidenceSurface never becomes a wire scalar anywhere.
    payload = emission_to_external_envelope(
        _emission(confidence=ConfidenceSurface(dimensions={"reliability": "high"}))
    )
    assert "confidence" not in json.dumps(payload)


def test_hints_never_carry_level():
    # the daemon classifies level itself (bot ADR-0024); the emitter stays advisory-minimal.
    payload = emission_to_external_envelope(_emission())
    assert "level" not in payload["candidate_hints"][0]


# --- provenance fields (#196) -> candidate_hints[].labels ---


def test_provenance_webhook_mode_in_labels():
    prov = ProviderProvenance(
        delivery_mode="webhook",
        verification="signed",
        provider_event_id="d-123",
        provider_resource_id="org/repo#42",
    )
    payload = emission_to_external_envelope(_emission(provenance=prov))
    _assert_conforms(payload)
    labels = _labels(payload)
    assert "delivery:webhook" in labels
    assert "verification:signed" in labels
    assert "provider_event_id:d-123" in labels
    assert "provider_resource_id:org/repo#42" in labels


def test_provenance_poll_mode_in_labels():
    prov = ProviderProvenance(delivery_mode="poll", verification="unsigned")
    payload = emission_to_external_envelope(_emission(provenance=prov))
    _assert_conforms(payload)
    labels = _labels(payload)
    assert "delivery:poll" in labels and "verification:unsigned" in labels
    assert not any(lbl.startswith("provider_event_id:") for lbl in labels)
    assert not any(lbl.startswith("provider_resource_id:") for lbl in labels)


def test_no_provenance_omits_provenance_labels():
    payload = emission_to_external_envelope(_emission())
    labels = _labels(payload)
    assert not any(lbl.startswith(("delivery:", "verification:", "provider_")) for lbl in labels)


# --- #198: emission_type lane hint (non-authoritative) ---


@pytest.mark.parametrize("et", ["evidence", "hint", "advisory", "candidate"])
def test_emission_type_carries_lane_label(et):
    payload = emission_to_external_envelope(_emission(emission_type=et))
    _assert_conforms(payload)
    assert f"emission_type:{et}" in _labels(payload)
    # The hint is advisory — no authority/lifecycle fields anywhere
    assert "level" not in payload["candidate_hints"][0]
    assert not (set(payload) & _FORBIDDEN_EXTERNAL_FIELDS)


def test_routing_hints_mapped_as_non_authoritative_labels():
    hints = (
        RoutingHint(role="security-reviewer", reason="Auth change", priority="high"),
        RoutingHint(role="data-owner", reason="PII scope"),
    )
    payload = emission_to_external_envelope(_emission(routing_hints=hints))
    _assert_conforms(payload)
    labels = _labels(payload)
    assert "routing:security-reviewer:high" in labels
    assert "routing:data-owner:normal" in labels


def test_advisories_mapped_as_non_authoritative_labels():
    advs = (
        AdvisoryResult(kind="dependency-risk", message="Upgrade numpy"),
        AdvisoryResult(kind="security-mention", message="Token rotation"),
    )
    payload = emission_to_external_envelope(_emission(advisories=advs))
    _assert_conforms(payload)
    labels = _labels(payload)
    assert "advisory:dependency-risk" in labels
    assert "advisory:security-mention" in labels


def test_combined_hints_all_non_authoritative():
    payload = emission_to_external_envelope(
        _emission(
            emission_type="advisory",
            routing_hints=(RoutingHint(role="arch-lead", reason="Boundary"),),
            advisories=(AdvisoryResult(kind="drift-risk", message="ADR-0008"),),
            confidence=ConfidenceSurface(dimensions={"relevance": "medium"}),
        )
    )
    _assert_conforms(payload)
    labels = _labels(payload)
    assert "emission_type:advisory" in labels
    assert "routing:arch-lead:normal" in labels
    assert "advisory:drift-risk" in labels
    assert "confidence" not in json.dumps(payload)  # never collapsed


def test_metadata_never_on_wire():
    payload = emission_to_external_envelope(
        _emission(metadata={"internal_key": "secret-ish-value", "debug": True})
    )
    _assert_conforms(payload)
    assert "metadata" not in payload
    assert "secret-ish-value" not in json.dumps(payload)


def test_bot_owned_fields_never_in_payload():
    for et in ("evidence", "hint", "advisory", "candidate"):
        payload = emission_to_external_envelope(_emission(emission_type=et))
        for field in BOT_OWNED_FIELDS:
            assert field not in payload, f"{field} leaked in {et} emission"
            assert field not in payload["candidate_hints"][0], f"{field} leaked in hint ({et})"


def test_no_emission_can_produce_authority_claims():
    payload = emission_to_external_envelope(
        _emission(
            emission_type="candidate",
            routing_hints=(RoutingHint(role="approver", reason="Review", priority="high"),),
            advisories=(AdvisoryResult(kind="binding-suggestion", message="Bind to symbol"),),
            confidence=ConfidenceSurface(dimensions={"authority": "high"}),
        )
    )
    payload_str = json.dumps(payload)
    assert not (set(payload) & _FORBIDDEN_EXTERNAL_FIELDS)
    for marker in ("ActorContext", "SourceSnapshot", "BindingEvidence", "signoff",
                   "compliance", "enforcement"):
        assert marker not in payload_str


def test_routing_hint_role_is_screened():
    hints = (RoutingHint(role="user@example.com", reason="Owner"),)
    payload = emission_to_external_envelope(_emission(routing_hints=hints))
    labels = _labels(payload)
    assert all("user@example.com" not in lbl for lbl in labels)
    assert any(lbl.startswith("routing:") for lbl in labels)  # redacted form survives


def test_advisory_kind_is_screened():
    advs = (AdvisoryResult(kind="alert-user@test.org", message="Notify"),)
    payload = emission_to_external_envelope(_emission(advisories=advs))
    assert all("user@test.org" not in lbl for lbl in _labels(payload))


def test_labels_are_contract_supported():
    # the v2 schema's advisory-string surface: ExternalCandidateHint.labels
    assert "labels" in _SCHEMA["definitions"]["ExternalCandidateHint"]["properties"]


def test_emission_without_hints_has_only_lane_label():
    payload = emission_to_external_envelope(_emission(emission_type="evidence"))
    assert _labels(payload) == ["emission_type:evidence"]


# --- GatewaySink (injected opener) ---


class _FakeResp:
    def __init__(self, status: int, body: bytes = b"") -> None:
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def read(self):
        return self._body


def _capabilities(**overrides):
    report = {
        "contract_id": EXTERNAL_INGEST_CONTRACT_ID,
        "protocol_version": 2,
        "minimum_supported_protocol_version": 2,
        "supported_protocol_versions": [2],
        "delivery_endpoint": "/api/v2/external-ingest",
        "request_schema_sha256": EXTERNAL_INGEST_REQUEST_SCHEMA_SHA256,
        "contract_fingerprint": EXTERNAL_INGEST_CONTRACT_FINGERPRINT,
        "redaction_receipt_required": True,
    }
    report.update(overrides)
    return report


def _valid_receipt():
    return {
        "schema_version": 1,
        "engine": "bicameral-stdlib-redaction",
        "engine_version": "1.0.0",
        "ruleset_id": "fx-sec-001-plus-pii-v1",
        "ruleset_digest": "sha256:" + "1" * 64,
        "input_digest": "sha256:" + "2" * 64,
        "output_digest": "sha256:" + "3" * 64,
        "findings": [{"category": "pii", "action": "tokenized", "count": 1}],
        "structural_fields_preserved": True,
        "completed_at": "2026-07-19T00:00:00Z",
    }


def _capture_opener(captured: dict, status: int = 201):
    def opener(request, timeout=None):
        if request.get_method() == "GET":
            captured["capabilities_url"] = request.full_url
            return _FakeResp(200, json.dumps(_capabilities()).encode("utf-8"))
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["content_type"] = request.get_header("Content-type")
        captured["authorization"] = request.get_header("Authorization")
        return _FakeResp(status)

    return opener


def test_gatewaysink_posts_conforming_envelope():
    captured: dict = {}
    sink = GatewaySink(
        endpoint="https://gw.example/api/v2/external-ingest",
        token=_TOKEN,
        opener=_capture_opener(captured),
    )
    sink.emit([_emission()])
    assert captured["method"] == "POST"
    assert captured["capabilities_url"].endswith("/api/external-ingest/capabilities")
    assert captured["url"].endswith("/api/v2/external-ingest")
    assert captured["content_type"] == "application/json"
    assert captured["authorization"] == f"Bearer {_TOKEN}"
    _assert_conforms(captured["body"], wire=True)


def test_gatewaysink_protocol_mismatch_stops_before_post():
    calls: list[str] = []

    def opener(request, timeout=None):
        calls.append(request.get_method())
        return _FakeResp(
            200,
            json.dumps(_capabilities(protocol_version=3)).encode("utf-8"),
        )

    sink = GatewaySink(
        endpoint="https://gw.example/api/v2/external-ingest", opener=opener
    )
    with pytest.raises(GatewayProtocolMismatch) as exc:
        sink.emit([_emission()])
    assert exc.value.reason == "protocol_mismatch:protocol_version_mismatch"
    assert calls == ["GET"]


def test_gatewaysink_contract_fingerprint_mismatch_stops_before_post():
    def opener(request, timeout=None):
        return _FakeResp(
            200,
            json.dumps(_capabilities(contract_fingerprint="0" * 64)).encode("utf-8"),
        )

    sink = GatewaySink(
        endpoint="https://gw.example/api/v2/external-ingest", opener=opener
    )
    with pytest.raises(GatewayProtocolMismatch) as exc:
        sink.emit([_emission()])
    assert exc.value.reason == "protocol_mismatch:contract_fingerprint_mismatch"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda receipt: receipt.update({"removed_value": "must-not-cross"}),
        lambda receipt: receipt["findings"][0].update({"category": "unbounded"}),
        lambda receipt: receipt["findings"][0].update({"count": 0}),
        lambda receipt: receipt.update({"completed_at": "yesterday"}),
    ],
)
def test_gatewaysink_receipt_runtime_matches_bot_schema(mutate):
    receipt = _valid_receipt()
    mutate(receipt)
    emission = _emission(metadata={"redaction_receipt": receipt})
    with pytest.raises(GatewayRedactionGated):
        GatewaySink(
            endpoint="https://gw.example/api/v2/external-ingest",
            opener=_capture_opener({}),
        ).emit([emission])


def test_gatewaysink_no_endpoint_is_gated():
    with pytest.raises(GatewayEmissionGated):
        GatewaySink().emit([_emission()])


def test_gatewaysink_no_token_sends_no_auth_header():
    captured: dict = {}
    GatewaySink(endpoint="https://gw/api/v2/external-ingest", opener=_capture_opener(captured)).emit(
        [_emission()]
    )
    assert captured["authorization"] is None


def test_gatewaysink_non_201_status_raises():
    sink = GatewaySink(
        endpoint="https://gw/api/v2/external-ingest", opener=_capture_opener({}, status=200)
    )
    with pytest.raises(GatewayEmissionError) as exc:
        sink.emit([_emission()])
    assert exc.value.status == 200


def _error_opener(code: int, body: bytes):
    def opener(request, timeout=None):
        if request.get_method() == "GET":
            return _FakeResp(200, json.dumps(_capabilities()).encode("utf-8"))
        raise urllib.error.HTTPError(request.full_url, code, "err", {}, io.BytesIO(body))

    return opener


def test_gatewaysink_403_fail_closed_token_free():
    # the gateway's authority-injection rejection surfaces as a terminal, token-free error.
    rejection = b'{"reason":"AuthorityInjection","message":"cannot carry authority fields"}'
    sink = GatewaySink(
        endpoint="https://gw/api/v2/external-ingest", token=_TOKEN,
        opener=_error_opener(403, rejection),
    )
    with pytest.raises(GatewayEmissionError) as exc:
        sink.emit([_emission()])
    assert exc.value.status == 403
    assert exc.value.reason == "gateway_rejected"
    assert _TOKEN not in str(exc.value)


def test_gatewaysink_422_status_preserved():
    sink = GatewaySink(
        endpoint="https://gw/api/v2/external-ingest", opener=_error_opener(422, b"{}")
    )
    with pytest.raises(GatewayEmissionError) as exc:
        sink.emit([_emission()])
    assert exc.value.status == 422


def test_gatewaysink_rejection_fixed_reason_no_body_reflection():
    # SECRET-LEAK-1 (purple-team 2026-06-11): the untrusted gateway response body is NOT
    # reflected into the error, even when it echoes the token back.
    leaky_body = b'{"reason":"' + _TOKEN.encode() + b'"}'
    sink = GatewaySink(
        endpoint="https://gw/api/v2/external-ingest",
        token=_TOKEN,
        opener=_error_opener(429, leaky_body),
    )
    with pytest.raises(GatewayEmissionError) as exc:
        sink.emit([_emission()])
    assert exc.value.status == 429
    assert exc.value.reason == "gateway_rejected"
    assert _TOKEN not in str(exc.value)


def test_gatewaysink_transport_error_raises_without_token():
    sink = GatewaySink(
        endpoint="https://gw/api/v2/external-ingest",
        token=_TOKEN,
        opener=_error_opener_url(),
    )
    with pytest.raises(GatewayEmissionError) as exc:
        sink.emit([_emission()])
    assert _TOKEN not in str(exc.value)


def _error_opener_url():
    def opener(request, timeout=None):
        raise urllib.error.URLError(OSError("connection refused"))

    return opener


def test_gatewaysink_revalidates_at_boundary():
    # F-1/F-2 + LD2: an evidence-less emission is refused BEFORE mapping/POST — which is also
    # what keeps the gateway's empty-evidence 422 unreachable from this path.
    bad = AdapterEmission(source_id="jira", title="t", body="b", evidence=(), adapter_version="x")
    with pytest.raises(EmissionContractError):
        GatewaySink(endpoint="https://gw/api/v2/external-ingest", opener=_capture_opener({})).emit([bad])


# --- one real urllib round-trip through a stdlib http.server (proves the POST path) ---


def test_gatewaysink_real_http_roundtrip():
    received: dict = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            received["capabilities_path"] = self.path
            body = json.dumps(_capabilities()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            received["body"] = json.loads(self.rfile.read(length).decode("utf-8"))
            received["path"] = self.path
            received["content_type"] = self.headers.get("Content-Type")
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"source_id":"s-1","advisory_results":[]}')

        def log_message(self, *_a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        sink = GatewaySink(endpoint=f"http://{host}:{port}/api/v2/external-ingest", timeout=5.0)
        sink.emit([_emission()])  # success on 201, no exception
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    _assert_conforms(received["body"], wire=True)
    assert received["capabilities_path"] == "/api/external-ingest/capabilities"
    assert received["path"] == "/api/v2/external-ingest"
    assert received["content_type"] == "application/json"


# --- #54: GatewaySink never leaks the operator token via CR/LF or unexpected errors ---


def test_token_with_crlf_rejected_at_construction():
    with pytest.raises(ValueError) as exc:
        GatewaySink(endpoint="https://gw/api/v2/external-ingest", token="SECRET-abc\r\nX-Evil: 1")
    assert "SECRET-abc" not in str(exc.value)  # message names the field, not the value


def test_header_with_crlf_rejected_at_construction():
    with pytest.raises(ValueError) as exc:
        GatewaySink(endpoint="https://gw/api/v2/external-ingest", headers={"X-Trace": "a\nb"})
    assert "a\nb" not in str(exc.value)


def test_post_unexpected_error_is_token_free():
    # an opener raising a bare ValueError that embeds the token -> token-free GatewayEmissionError.
    token = "SUPERSECRET-xyz"

    def opener(request, timeout=None):
        if request.get_method() == "GET":
            return _FakeResp(200, json.dumps(_capabilities()).encode("utf-8"))
        raise ValueError(f"Invalid header value b'Bearer {token}'")

    sink = GatewaySink(endpoint="https://gw/api/v2/external-ingest", token=token, opener=opener)
    with pytest.raises(GatewayEmissionError) as exc:
        sink.emit([_emission()])
    assert token not in str(exc.value)
