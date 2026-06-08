# SPDX-License-Identifier: MIT
"""Behavior tests for the live single-document GET fetch path (FX-GDRIVE-002; ADR-0012).

Proven through a recording transport over a crafted Google Docs ``documents.get`` response —
the GET URL + Bearer header, fail-closed on every untrusted edge, the FX-SEC-001 screen, and the
fullmatch path-injection guard — without any live network (a mock does not promote to Live).
"""

from __future__ import annotations

import json

import pytest

from adapter.core.pipeline import EmissionContractError
from runtime.doc_fetch import DocFetchSpec, fetch_document
from runtime.poll_auth import PollError
from runtime.poll_client import HttpResponse
from runtime.poll_specs import build_google_drive_spec
from runtime.secrets import MappingSecretResolver
from runtime.sinks import CollectingSink

_AKIA = "AKIAIOSFODNN7EXAMPLE"  # fake AWS key shape
_DOC_ID = "1AbcDEF_ghi-jklMNOpqrstuvWXYZ0123456789"  # valid id grammar
_DOCS_BASE = "https://docs.googleapis.com/v1/documents/"


class _RecordingTransport:
    def __init__(self, response: HttpResponse) -> None:
        self._response = response
        self.calls: list[tuple] = []

    def request(self, method, url, *, headers, body=None):
        self.calls.append((method, url, headers))
        return self._response


def _doc(text: str = "Hello world") -> dict:
    return {"documentId": _DOC_ID, "title": "Q3 Plan", "body": {"content": [
        {"paragraph": {"elements": [{"textRun": {"content": text + "\n"}}],
                       "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}}},
    ]}}


def _resp(status: int, payload: object) -> HttpResponse:
    return HttpResponse(status, json.dumps(payload).encode("utf-8"))


def _spec() -> DocFetchSpec:
    return build_google_drive_spec(MappingSecretResolver({"google_drive": "ya29.tok"}), document_id=_DOC_ID)


def test_fetch_document_emits():
    transport = _RecordingTransport(_resp(200, _doc()))
    sink = CollectingSink()
    count = fetch_document(_spec(), transport, sink)
    assert count == 1
    method, url, headers = transport.calls[0]
    assert method == "GET" and url == _DOCS_BASE + _DOC_ID
    assert headers["Authorization"] == "Bearer ya29.tok"


def test_fetch_non_200_fails_closed():
    transport = _RecordingTransport(_resp(404, {"error": "not found"}))
    with pytest.raises(PollError) as exc:
        fetch_document(_spec(), transport, CollectingSink())
    assert exc.value.reason == "http_error"


def test_fetch_oversized_body_fails_closed(monkeypatch):
    import runtime.doc_fetch as df
    monkeypatch.setattr(df, "_MAX_RESPONSE", 10)
    transport = _RecordingTransport(_resp(200, _doc()))  # body > 10 bytes
    with pytest.raises(PollError) as exc:
        fetch_document(_spec(), transport, CollectingSink())
    assert exc.value.reason == "oversized_body"


def test_fetch_non_object_body_fails_closed():
    for payload in ([{"documentId": _DOC_ID}], "a-bare-string", 42, None):
        transport = _RecordingTransport(_resp(200, payload))
        with pytest.raises(PollError) as exc:
            fetch_document(_spec(), transport, CollectingSink())
        assert exc.value.reason == "non_object_body"


def test_fetch_secret_in_doc_text_rejected():
    # FX-SEC-001: a secret in the document body is HARD-rejected by normalize, never emitted.
    transport = _RecordingTransport(_resp(200, _doc(text=f"deploy key {_AKIA}")))
    sink = CollectingSink()
    with pytest.raises(EmissionContractError):
        fetch_document(_spec(), transport, sink)
    assert not sink.emissions


def test_blank_token_makes_no_request():
    with pytest.raises(PollError) as exc:
        build_google_drive_spec(MappingSecretResolver({"google_drive": ""}), document_id=_DOC_ID)
    assert exc.value.reason == "secret_unresolved:google_drive"


@pytest.mark.parametrize("bad_id", [
    "x/../y",          # embedded traversal on a valid prefix
    "x?alt=media",     # query injection
    "x#frag",          # fragment
    "x@evil.com",      # userinfo / host swap
    "a" * 201,         # over-length
    "x\r\nHost: evil", # control chars / header split
    "",                # empty
])
def test_bad_document_id_rejected(bad_id):
    # the fullmatch guard fires BEFORE secret resolution / any request.
    with pytest.raises(PollError) as exc:
        build_google_drive_spec(MappingSecretResolver({"google_drive": "ya29.tok"}), document_id=bad_id)
    assert exc.value.reason == "bad_document_id"
