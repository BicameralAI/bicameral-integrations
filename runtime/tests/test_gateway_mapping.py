# SPDX-License-Identifier: MIT
"""Tests for the Live emission seam: AdapterEmission -> v2 ExternalIngestEnvelope + GatewaySink (#226).

The vendored schema ``runtime/schemas/external_ingest_request_v2.schema.json`` is a byte-exact copy
of ``bicameral-bot:protocol/schemas/v2/external-ingest-request.schema.json`` pinned at schema commit
``5c24c60fcba8ed9d04ab5dd6fd0977dcddd9bd57`` (bot HEAD ``22806ac21125b497370786f2ad400b8ba44365cf``).
The forbidden-authority list mirrors ``bicameral-bot:crates/bicameral-gateway/src/routes.rs:500-521``
(18 names; the gateway 403s any of them at the top level).
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
    ConfidenceSurface,
    SourceEvidence,
    SourceRef,
)
from adapter.core.pipeline import EmissionContractError
from runtime import GatewayEmissionError, GatewayEmissionGated, GatewaySink, emission_to_external_envelope

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


def _assert_conforms(payload: dict) -> None:
    """Emitter-side strict conformance against the vendored v2 schema. NOTE: the gateway itself
    IGNORES unknown non-forbidden top-level keys (the schema carries no additionalProperties
    guard) — the key-set restriction here is the EMITTER's own discipline, locked so an
    accidental extra field can never drift toward the 403'd authority set."""
    assert set(payload) <= set(_SCHEMA["properties"]), "extra top-level key vs emitter discipline"
    for key in _SCHEMA["required"]:  # content, source_system, source_uri
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


# --- mapping ---


def test_mapping_conforms_to_vendored_v2_schema():
    payload = emission_to_external_envelope(_emission())
    _assert_conforms(payload)
    assert payload["source_system"] == "jira"
    assert payload["source_uri"] == "https://example.atlassian.net/browse/ENG-1"
    assert payload["content"] == "The team decided to adopt OAuth."
    assert payload["evidence"] == [{"excerpt": "Decided to adopt OAuth."}]
    assert payload["candidate_hints"] == [
        {"title": "Adopt OAuth", "body": "The team decided to adopt OAuth."}
    ]


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


def test_hints_never_carry_level_or_labels():
    # the daemon classifies level itself (bot ADR-0024); the emitter stays advisory-minimal.
    payload = emission_to_external_envelope(_emission())
    hint = payload["candidate_hints"][0]
    assert "level" not in hint and "labels" not in hint


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


def test_gatewaysink_posts_conforming_envelope():
    captured: dict = {}
    sink = GatewaySink(
        endpoint="https://gw.example/api/v1/external-ingest",
        token=_TOKEN,
        opener=_capture_opener(captured),
    )
    sink.emit([_emission()])
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/api/v1/external-ingest")
    assert captured["content_type"] == "application/json"
    assert captured["authorization"] == f"Bearer {_TOKEN}"
    _assert_conforms(captured["body"])


def test_gatewaysink_no_endpoint_is_gated():
    with pytest.raises(GatewayEmissionGated):
        GatewaySink().emit([_emission()])


def test_gatewaysink_no_token_sends_no_auth_header():
    captured: dict = {}
    GatewaySink(endpoint="https://gw/api/v1/external-ingest", opener=_capture_opener(captured)).emit(
        [_emission()]
    )
    assert captured["authorization"] is None


def test_gatewaysink_non_201_status_raises():
    sink = GatewaySink(
        endpoint="https://gw/api/v1/external-ingest", opener=_capture_opener({}, status=200)
    )
    with pytest.raises(GatewayEmissionError) as exc:
        sink.emit([_emission()])
    assert exc.value.status == 200


def _error_opener(code: int, body: bytes):
    def opener(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, code, "err", {}, io.BytesIO(body))

    return opener


def test_gatewaysink_403_fail_closed_token_free():
    # the gateway's authority-injection rejection surfaces as a terminal, token-free error.
    rejection = b'{"reason":"AuthorityInjection","message":"cannot carry authority fields"}'
    sink = GatewaySink(
        endpoint="https://gw/api/v1/external-ingest", token=_TOKEN,
        opener=_error_opener(403, rejection),
    )
    with pytest.raises(GatewayEmissionError) as exc:
        sink.emit([_emission()])
    assert exc.value.status == 403
    assert exc.value.reason == "gateway_rejected"
    assert _TOKEN not in str(exc.value)


def test_gatewaysink_422_status_preserved():
    sink = GatewaySink(
        endpoint="https://gw/api/v1/external-ingest", opener=_error_opener(422, b"{}")
    )
    with pytest.raises(GatewayEmissionError) as exc:
        sink.emit([_emission()])
    assert exc.value.status == 422


def test_gatewaysink_rejection_fixed_reason_no_body_reflection():
    # SECRET-LEAK-1 (purple-team 2026-06-11): the untrusted gateway response body is NOT
    # reflected into the error, even when it echoes the token back.
    leaky_body = b'{"reason":"' + _TOKEN.encode() + b'"}'
    sink = GatewaySink(
        endpoint="https://gw/api/v1/external-ingest",
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
        endpoint="https://gw/api/v1/external-ingest",
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
        GatewaySink(endpoint="https://gw/api/v1/external-ingest", opener=_capture_opener({})).emit([bad])


# --- one real urllib round-trip through a stdlib http.server (proves the POST path) ---


def test_gatewaysink_real_http_roundtrip():
    received: dict = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
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
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        sink = GatewaySink(endpoint=f"http://{host}:{port}/api/v1/external-ingest", timeout=5.0)
        sink.emit([_emission()])  # success on 201, no exception
    finally:
        thread.join(timeout=5)
        server.server_close()
    _assert_conforms(received["body"])
    assert received["path"] == "/api/v1/external-ingest"
    assert received["content_type"] == "application/json"


# --- #54: GatewaySink never leaks the operator token via CR/LF or unexpected errors ---


def test_token_with_crlf_rejected_at_construction():
    with pytest.raises(ValueError) as exc:
        GatewaySink(endpoint="https://gw/api/v1/external-ingest", token="SECRET-abc\r\nX-Evil: 1")
    assert "SECRET-abc" not in str(exc.value)  # message names the field, not the value


def test_header_with_crlf_rejected_at_construction():
    with pytest.raises(ValueError) as exc:
        GatewaySink(endpoint="https://gw/api/v1/external-ingest", headers={"X-Trace": "a\nb"})
    assert "a\nb" not in str(exc.value)


def test_post_unexpected_error_is_token_free():
    # an opener raising a bare ValueError that embeds the token -> token-free GatewayEmissionError.
    token = "SUPERSECRET-xyz"

    def opener(request, timeout=None):
        raise ValueError(f"Invalid header value b'Bearer {token}'")

    sink = GatewaySink(endpoint="https://gw/api/v1/external-ingest", token=token, opener=opener)
    with pytest.raises(GatewayEmissionError) as exc:
        sink.emit([_emission()])
    assert token not in str(exc.value)
