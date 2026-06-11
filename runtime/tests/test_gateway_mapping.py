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
    ConfidenceSurface,
    SourceEvidence,
    SourceRef,
)
from adapter.core.pipeline import EmissionContractError
from runtime import GatewayEmissionError, GatewayEmissionGated, GatewaySink, emission_to_ingest_request

_SCHEMA = json.loads(
    (Path(__file__).resolve().parents[1] / "schemas" / "ingest_request_v1.schema.json").read_text(
        encoding="utf-8"
    )
)
_TOKEN = "super-secret-operator-token"


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


def test_required_fields_are_floored():
    ev = SourceEvidence(
        source_ref=SourceRef(source_id="jira", ref="ENG-9", url=""), excerpt="Fallback excerpt."
    )
    e = AdapterEmission(source_id="jira", title="   ", body="", evidence=(ev,), adapter_version="x")
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
        endpoint="https://gw.example/api/v1/ingest", token=_TOKEN, opener=_capture_opener(captured)
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
    GatewaySink(endpoint="https://gw/api/v1/ingest", opener=_capture_opener(captured)).emit(
        [_emission()]
    )
    assert captured["authorization"] is None


def test_gatewaysink_non_201_status_raises():
    sink = GatewaySink(endpoint="https://gw/api/v1/ingest", opener=_capture_opener({}, status=200))
    with pytest.raises(GatewayEmissionError) as exc:
        sink.emit([_emission()])
    assert exc.value.status == 200


def _error_opener(code: int, body: bytes):
    def opener(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, code, "err", {}, io.BytesIO(body))

    return opener


def test_gatewaysink_rejection_fixed_reason_no_body_reflection():
    # SECRET-LEAK-1 (purple-team 2026-06-11): the untrusted gateway response body is NOT
    # reflected into the error. A gateway that echoes the request (incl. the Authorization
    # header) into its rejection body must not leak the token; status still disambiguates.
    leaky_body = b'{"reason":"' + _TOKEN.encode() + b'"}'  # gateway echoes the token back
    sink = GatewaySink(
        endpoint="https://gw/api/v1/ingest",
        token=_TOKEN,
        opener=_error_opener(429, leaky_body),
    )
    with pytest.raises(GatewayEmissionError) as exc:
        sink.emit([_emission()])
    assert exc.value.status == 429                  # status preserved (retryable vs terminal)
    assert exc.value.reason == "gateway_rejected"   # fixed discriminator, body not reflected
    assert _TOKEN not in str(exc.value)             # token never in the error, even if echoed


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
    bad = AdapterEmission(source_id="jira", title="t", body="b", evidence=(), adapter_version="x")
    with pytest.raises(EmissionContractError):
        GatewaySink(endpoint="https://gw/api/v1/ingest", opener=_capture_opener({})).emit([bad])


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
        GatewaySink(endpoint="https://gw/api/v1/ingest", token="SECRET-abc\r\nX-Evil: 1")
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
