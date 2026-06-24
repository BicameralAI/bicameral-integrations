# SPDX-License-Identifier: MIT
"""Tests for the Live emission seam: AdapterEmission -> v1 IngestRequest + GatewaySink."""

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
    GatewaySink,
    emission_to_ingest_request,
)
from runtime.gateway_mapping import BOT_OWNED_FIELDS

_SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "schemas"
        / "ingest_request_v1.schema.json"
    ).read_text(encoding="utf-8")
)
_TOKEN = "super-secret-operator-token"


def _emission(**kw) -> AdapterEmission:
    ev = SourceEvidence(
        source_ref=SourceRef(
            source_id="jira",
            ref="ENG-1",
            url="https://example.atlassian.net/browse/ENG-1",
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


def _assert_conforms(payload: dict) -> None:
    for key in _SCHEMA["required"]:  # title, description, source
        assert key in payload and isinstance(payload[key], str) and payload[key]
    assert isinstance(payload["evidence"], list) and payload["evidence"]
    item_required = _SCHEMA["definitions"]["IngestEvidenceItem"]["required"]  # excerpt
    for item in payload["evidence"]:
        for k in item_required:
            assert k in item and isinstance(item[k], str) and item[k]


# --- mapping ---


def test_mapping_conforms_to_vendored_v1_schema():
    payload = emission_to_ingest_request(_emission())
    _assert_conforms(payload)
    assert payload["title"] == "Adopt OAuth"
    assert payload["description"] == "The team decided to adopt OAuth."
    assert payload["source"] == "https://example.atlassian.net/browse/ENG-1"
    assert payload["source_type"] == "jira"
    assert payload["evidence"] == [{"excerpt": "Decided to adopt OAuth."}]
    # default emission_type is "candidate" -> label + tags carry the lane hint
    assert payload["label"] == "emission_type:candidate"
    assert "emission_type:candidate" in payload["tags"]


def test_required_fields_are_floored():
    ev = SourceEvidence(
        source_ref=SourceRef(source_id="jira", ref="ENG-9", url=""),
        excerpt="Fallback excerpt.",
    )
    e = AdapterEmission(
        source_id="jira", title="   ", body="", evidence=(ev,), adapter_version="x"
    )
    payload = emission_to_ingest_request(e)
    _assert_conforms(payload)
    assert payload["title"] == "Fallback excerpt."
    assert payload["description"] == "Fallback excerpt."
    assert payload["source"] == "jira:ENG-9"  # no url -> source_id:ref


def test_dimensional_confidence_not_collapsed_to_scalar():
    payload = emission_to_ingest_request(
        _emission(confidence=ConfidenceSurface(dimensions={"reliability": "high"}))
    )
    assert all("confidence" not in item for item in payload["evidence"])


# --- provenance fields (#196) ---


def test_provenance_webhook_mode_in_payload():
    prov = ProviderProvenance(
        delivery_mode="webhook",
        verification="signed",
        provider_event_id="d-123",
        provider_resource_id="org/repo#42",
    )
    payload = emission_to_ingest_request(_emission(provenance=prov))
    _assert_conforms(payload)
    assert payload["delivery_mode"] == "webhook"
    assert payload["verification"] == "signed"
    assert payload["provider_event_id"] == "d-123"
    assert payload["provider_resource_id"] == "org/repo#42"


def test_provenance_poll_mode_in_payload():
    prov = ProviderProvenance(
        delivery_mode="poll",
        verification="unsigned",
    )
    payload = emission_to_ingest_request(_emission(provenance=prov))
    _assert_conforms(payload)
    assert payload["delivery_mode"] == "poll"
    assert payload["verification"] == "unsigned"
    assert "provider_event_id" not in payload
    assert "provider_resource_id" not in payload


def test_provenance_active_fetch_mode_in_payload():
    prov = ProviderProvenance(
        delivery_mode="active-fetch",
        verification="unsigned",
        provider_resource_id="res-1",
    )
    payload = emission_to_ingest_request(_emission(provenance=prov))
    _assert_conforms(payload)
    assert payload["delivery_mode"] == "active-fetch"
    assert payload["verification"] == "unsigned"
    assert "provider_event_id" not in payload
    assert payload["provider_resource_id"] == "res-1"


def test_no_provenance_omits_fields():
    payload = emission_to_ingest_request(_emission())
    _assert_conforms(payload)
    assert "delivery_mode" not in payload
    assert "verification" not in payload
    assert "provider_event_id" not in payload
    assert "provider_resource_id" not in payload



# --- #198: field classification — emission_type lane hint (non-authoritative) ---


def test_evidence_emission_carries_lane_hint():
    """An evidence emission carries emission_type as a non-authoritative lane hint."""
    payload = emission_to_ingest_request(_emission(emission_type="evidence"))
    _assert_conforms(payload)
    assert payload["label"] == "emission_type:evidence"
    assert "emission_type:evidence" in payload["tags"]
    # The hint is advisory — no authority fields present
    assert "level" not in payload
    assert "snapshot_content" not in payload


def test_hint_emission_carries_lane_hint():
    """A hint emission carries emission_type as a non-authoritative lane hint."""
    payload = emission_to_ingest_request(_emission(emission_type="hint"))
    _assert_conforms(payload)
    assert payload["label"] == "emission_type:hint"
    assert "emission_type:hint" in payload["tags"]


def test_advisory_emission_carries_lane_hint():
    """An advisory emission carries emission_type as a non-authoritative lane hint."""
    payload = emission_to_ingest_request(_emission(emission_type="advisory"))
    _assert_conforms(payload)
    assert payload["label"] == "emission_type:advisory"
    assert "emission_type:advisory" in payload["tags"]


def test_candidate_emission_is_non_authoritative():
    """A candidate-like emission is mapped as a hint, never as an accepted candidate."""
    payload = emission_to_ingest_request(_emission(emission_type="candidate"))
    _assert_conforms(payload)
    assert payload["label"] == "emission_type:candidate"
    # Non-authoritative: no level, no accepted state, no bot-owned lifecycle
    assert "level" not in payload
    assert "snapshot_content" not in payload
    # emission_type:candidate is a lane HINT, not an accepted decision
    assert all(
        not tag.startswith("accepted:") and not tag.startswith("binding:")
        for tag in payload["tags"]
    )


# --- #198: routing hints — screened, non-authoritative ---


def test_routing_hints_mapped_as_non_authoritative_tags():
    """Routing hints are screened and mapped to tags; they never encode authority."""
    hints = (
        RoutingHint(role="security-reviewer", reason="Auth change", priority="high"),
        RoutingHint(role="data-owner", reason="PII scope"),
    )
    payload = emission_to_ingest_request(_emission(routing_hints=hints))
    _assert_conforms(payload)
    assert "routing:security-reviewer:high" in payload["tags"]
    assert "routing:data-owner:normal" in payload["tags"]
    # Non-authoritative: no level, no authority claims
    assert "level" not in payload


def test_advisories_mapped_as_non_authoritative_tags():
    """Advisory results are screened and mapped to tags; they never encode authority."""
    advs = (
        AdvisoryResult(kind="dependency-risk", message="Upgrade numpy"),
        AdvisoryResult(kind="security-mention", message="Token rotation"),
    )
    payload = emission_to_ingest_request(_emission(advisories=advs))
    _assert_conforms(payload)
    assert "advisory:dependency-risk" in payload["tags"]
    assert "advisory:security-mention" in payload["tags"]


def test_combined_hints_all_non_authoritative():
    """An emission with all hint types produces tags but no authority claims."""
    payload = emission_to_ingest_request(
        _emission(
            emission_type="advisory",
            routing_hints=(RoutingHint(role="arch-lead", reason="Boundary"),),
            advisories=(AdvisoryResult(kind="drift-risk", message="ADR-0008"),),
            confidence=ConfidenceSurface(dimensions={"relevance": "medium"}),
        )
    )
    _assert_conforms(payload)
    assert payload["label"] == "emission_type:advisory"
    assert "emission_type:advisory" in payload["tags"]
    assert "routing:arch-lead:normal" in payload["tags"]
    assert "advisory:drift-risk" in payload["tags"]
    # confidence is NOT collapsed
    assert "confidence" not in payload
    assert all("confidence" not in item for item in payload["evidence"])


# --- #198: unscreened metadata stays off the wire ---


def test_metadata_never_on_wire():
    """Emission metadata is never forwarded — FX-SEC-001 does not screen it."""
    payload = emission_to_ingest_request(
        _emission(metadata={"internal_key": "secret-ish-value", "debug": True})
    )
    _assert_conforms(payload)
    assert "metadata" not in payload
    assert "internal_key" not in str(payload)
    assert "secret-ish-value" not in str(payload)


# --- #198: bot-owned fields are never sent ---


def test_bot_owned_fields_never_in_payload():
    """Bot-owned fields (level, snapshot_content, ActorContext, etc.) never appear."""
    for et in ("evidence", "hint", "advisory", "candidate"):
        payload = emission_to_ingest_request(_emission(emission_type=et))
        for field in BOT_OWNED_FIELDS:
            assert field not in payload, f"{field} leaked in {et} emission"


def test_no_emission_can_produce_authority_claims():
    """No combination of emission fields can produce accepted-state or binding tags."""
    payload = emission_to_ingest_request(
        _emission(
            emission_type="candidate",
            routing_hints=(
                RoutingHint(role="approver", reason="Review", priority="high"),
            ),
            advisories=(
                AdvisoryResult(kind="binding-suggestion", message="Bind to symbol"),
            ),
            confidence=ConfidenceSurface(dimensions={"authority": "high"}),
        )
    )
    payload_str = json.dumps(payload)
    # No accepted/canonical state
    assert '"status"' not in payload_str or '"raw"' in payload_str
    # No bot lifecycle fields
    assert "ActorContext" not in payload_str
    assert "SourceSnapshot" not in payload_str
    assert "BindingEvidence" not in payload_str
    assert "signoff" not in payload_str
    assert "compliance" not in payload_str
    assert "enforcement" not in payload_str


# --- #198: routing/advisory hints are screened ---


def test_routing_hint_role_is_screened():
    """A routing hint role containing PII is redacted before mapping."""
    hints = (RoutingHint(role="user@example.com", reason="Owner"),)
    payload = emission_to_ingest_request(_emission(routing_hints=hints))
    tags = payload.get("tags", [])
    # Email in role is redacted
    assert all("user@example.com" not in t for t in tags)
    # But some routing tag still exists (redacted form)
    assert any(t.startswith("routing:") for t in tags)


def test_advisory_kind_is_screened():
    """An advisory kind containing PII is redacted before mapping."""
    advs = (AdvisoryResult(kind="alert-user@test.org", message="Notify"),)
    payload = emission_to_ingest_request(_emission(advisories=advs))
    tags = payload.get("tags", [])
    assert all("user@test.org" not in t for t in tags)


# --- #198: schema conformance for hint fields ---


def _schema_allows_field(field: str) -> bool:
    return field in _SCHEMA.get("properties", {})


def test_label_and_tags_are_contract_supported():
    """The vendored v1 schema supports label and tags (hint fields)."""
    assert _schema_allows_field("label"), "label not in vendored schema"
    assert _schema_allows_field("tags"), "tags not in vendored schema"


def test_emission_without_hints_has_no_label_or_routing_tags():
    """A bare evidence emission with no routing/advisory has only the lane tag."""
    payload = emission_to_ingest_request(_emission(emission_type="evidence"))
    assert payload["label"] == "emission_type:evidence"
    assert payload["tags"] == ["emission_type:evidence"]


# --- GatewaySink (injected opener) ---


class _FakeResp:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _capture_opener(captured: dict, status: int = 201):
    def opener(request, timeout=None):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["content_type"] = request.get_header("Content-type")
        captured["authorization"] = request.get_header("Authorization")
        return _FakeResp(status)

    return opener


def test_gatewaysink_posts_conforming_request():
    captured: dict = {}
    sink = GatewaySink(
        endpoint="https://gw.example/api/v1/ingest",
        token=_TOKEN,
        opener=_capture_opener(captured),
    )
    sink.emit([_emission()])
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/api/v1/ingest")
    assert captured["content_type"] == "application/json"
    assert captured["authorization"] == f"Bearer {_TOKEN}"
    _assert_conforms(captured["body"])


def test_gatewaysink_no_endpoint_is_gated():
    with pytest.raises(GatewayEmissionGated):
        GatewaySink().emit([_emission()])


def test_gatewaysink_no_token_sends_no_auth_header():
    captured: dict = {}
    GatewaySink(
        endpoint="https://gw/api/v1/ingest", opener=_capture_opener(captured)
    ).emit([_emission()])
    assert captured["authorization"] is None


def test_gatewaysink_non_201_status_raises():
    sink = GatewaySink(
        endpoint="https://gw/api/v1/ingest", opener=_capture_opener({}, status=200)
    )
    with pytest.raises(GatewayEmissionError) as exc:
        sink.emit([_emission()])
    assert exc.value.status == 200


def _error_opener(code: int, body: bytes):
    def opener(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url, code, "err", {}, io.BytesIO(body)
        )

    return opener


def test_gatewaysink_rejection_fixed_reason_no_body_reflection():
    # SECRET-LEAK-1 (purple-team 2026-06-11): the untrusted gateway response body is NOT
    # reflected into the error. A gateway that echoes the request (incl. the Authorization
    # header) into its rejection body must not leak the token; status still disambiguates.
    leaky_body = (
        b'{"reason":"' + _TOKEN.encode() + b'"}'
    )  # gateway echoes the token back
    sink = GatewaySink(
        endpoint="https://gw/api/v1/ingest",
        token=_TOKEN,
        opener=_error_opener(429, leaky_body),
    )
    with pytest.raises(GatewayEmissionError) as exc:
        sink.emit([_emission()])
    assert exc.value.status == 429  # status preserved (retryable vs terminal)
    assert (
        exc.value.reason == "gateway_rejected"
    )  # fixed discriminator, body not reflected
    assert _TOKEN not in str(exc.value)  # token never in the error, even if echoed


def test_gatewaysink_transport_error_raises_without_token():
    sink = GatewaySink(
        endpoint="https://gw/api/v1/ingest",
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
    # F-1/F-2: a hand-built emission with no evidence is refused before any POST.
    bad = AdapterEmission(
        source_id="jira", title="t", body="b", evidence=(), adapter_version="x"
    )
    with pytest.raises(EmissionContractError):
        GatewaySink(
            endpoint="https://gw/api/v1/ingest", opener=_capture_opener({})
        ).emit([bad])


# --- one real urllib round-trip through a stdlib http.server (proves the POST path) ---


def test_gatewaysink_real_http_roundtrip():
    received: dict = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            received["body"] = json.loads(self.rfile.read(length).decode("utf-8"))
            received["content_type"] = self.headers.get("Content-Type")
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"candidate_id":"c-1"}')

        def log_message(self, *_a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        sink = GatewaySink(endpoint=f"http://{host}:{port}/api/v1/ingest", timeout=5.0)
        sink.emit([_emission()])  # success on 201, no exception
    finally:
        thread.join(timeout=5)
        server.server_close()
    _assert_conforms(received["body"])
    assert received["content_type"] == "application/json"


# --- #54: GatewaySink never leaks the operator token via CR/LF or unexpected errors ---


def test_token_with_crlf_rejected_at_construction():
    with pytest.raises(ValueError) as exc:
        GatewaySink(
            endpoint="https://gw/api/v1/ingest", token="SECRET-abc\r\nX-Evil: 1"
        )
    assert "SECRET-abc" not in str(exc.value)  # message names the field, not the value


def test_header_with_crlf_rejected_at_construction():
    with pytest.raises(ValueError) as exc:
        GatewaySink(endpoint="https://gw/api/v1/ingest", headers={"X-Trace": "a\nb"})
    assert "a\nb" not in str(exc.value)


def test_post_unexpected_error_is_token_free():
    # an opener raising a bare ValueError that embeds the token -> token-free GatewayEmissionError.
    token = "SUPERSECRET-xyz"

    def opener(request, timeout=None):
        raise ValueError(f"Invalid header value b'Bearer {token}'")

    sink = GatewaySink(endpoint="https://gw/api/v1/ingest", token=token, opener=opener)
    with pytest.raises(GatewayEmissionError) as exc:
        sink.emit([_emission()])
    assert token not in str(exc.value)
