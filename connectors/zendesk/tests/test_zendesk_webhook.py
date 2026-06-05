# SPDX-License-Identifier: MIT
"""Behavioral tests for ZendeskConnector webhook verify + dedup (Base64 HMAC)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path

from adapter.core.webhook_security import DeliveryDedupCache
from connectors.zendesk.connector import ZendeskConnector

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ticket_event.json"
_SECRET = "zendesk-signing-secret"
_TS = "2026-06-03T10:00:00Z"


def _body() -> bytes:
    return json.dumps(json.loads(_FIXTURE.read_text(encoding="utf-8"))).encode("utf-8")


def _sig(body: bytes, ts: str = _TS) -> str:
    return base64.b64encode(
        hmac.new(_SECRET.encode(), ts.encode() + body, hashlib.sha256).digest()
    ).decode("ascii")


def _headers(body: bytes, ts: str = _TS) -> dict[str, str]:
    return {
        "X-Zendesk-Webhook-Signature": _sig(body, ts),
        "X-Zendesk-Webhook-Signature-Timestamp": ts,
    }


def test_verify_true_for_valid_signature():
    body = _body()
    assert ZendeskConnector(secret=_SECRET).verify(headers=_headers(body), body=body) is True


def test_verify_false_for_tampered_body():
    body = _body()
    assert ZendeskConnector(secret=_SECRET).verify(headers=_headers(body), body=body + b" ") is False


def test_verify_false_for_missing_header():
    body = _body()
    assert ZendeskConnector(secret=_SECRET).verify(headers={}, body=body) is False


def test_normalize_event_parses_after_verify():
    body = _body()
    out = ZendeskConnector(secret=_SECRET).normalize_event(headers=_headers(body), body=body)
    assert len(out) == 1
    assert out[0].source_ref.source_id == "zendesk"
    assert out[0].source_ref.ref == "4571"


def test_normalize_event_rejects_bad_signature():
    body = _body()
    conn = ZendeskConnector(secret=_SECRET)
    bad = {"X-Zendesk-Webhook-Signature": "bad", "X-Zendesk-Webhook-Signature-Timestamp": _TS}
    assert conn.normalize_event(headers=bad, body=body) == []


def test_normalize_event_dedup_second_delivery_returns_empty():
    body = _body()
    conn = ZendeskConnector(secret=_SECRET, dedup=DeliveryDedupCache())
    assert len(conn.normalize_event(headers=_headers(body), body=body)) == 1
    assert conn.normalize_event(headers=_headers(body), body=body) == []
