# SPDX-License-Identifier: MIT
"""Behavioral tests for SlackConnector webhook verify + dedup (v0 signing)."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from adapter.core.webhook_security import DeliveryDedupCache
from connectors.slack.connector import SlackConnector

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "webhook_message.json"
_SECRET = "slack-signing-secret"
_TS = "1700000000"


def _body() -> bytes:
    return json.dumps(json.loads(_FIXTURE.read_text(encoding="utf-8"))).encode("utf-8")


def _sig(body: bytes, ts: str = _TS) -> str:
    base = b"v0:" + ts.encode() + b":" + body
    return "v0=" + hmac.new(_SECRET.encode(), base, hashlib.sha256).hexdigest()


def _headers(body: bytes, ts: str = _TS) -> dict[str, str]:
    return {"X-Slack-Signature": _sig(body, ts), "X-Slack-Request-Timestamp": ts}


def _conn(**kw) -> SlackConnector:
    return SlackConnector(secret=_SECRET, clock=lambda: float(_TS), **kw)


def test_verify_true_for_valid_signature():
    body = _body()
    assert _conn().verify(headers=_headers(body), body=body) is True


def test_verify_false_for_tampered_body_with_fresh_timestamp():
    # body changes but timestamp stays valid -> proves the body is in the basestring.
    body = _body()
    assert _conn().verify(headers=_headers(body), body=body + b"!") is False


def test_verify_false_for_stale_timestamp():
    # connector clock pushed > 300 s past the signed timestamp -> replay window.
    body = _body()
    conn = SlackConnector(secret=_SECRET, clock=lambda: float(_TS) + 1000)
    assert conn.verify(headers=_headers(body), body=body) is False


def test_verify_false_for_missing_header():
    body = _body()
    assert _conn().verify(headers={}, body=body) is False


def test_normalize_event_parses_after_verify():
    body = _body()
    out = _conn().normalize_event(headers=_headers(body), body=body)
    assert len(out) == 1 and out[0].source_ref.source_id == "slack"


def test_normalize_event_url_verification_handshake_returns_empty():
    body = json.dumps({"type": "url_verification", "challenge": "abc"}).encode("utf-8")
    assert _conn().normalize_event(headers=_headers(body), body=body) == []


def test_normalize_event_dedup_second_delivery_returns_empty():
    body = _body()
    conn = _conn(dedup=DeliveryDedupCache())
    assert len(conn.normalize_event(headers=_headers(body), body=body)) == 1
    assert conn.normalize_event(headers=_headers(body), body=body) == []
