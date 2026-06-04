"""Behavioral tests for LinearConnector webhook verify + dedup (Linear-Signature)."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from adapter.core.webhook_security import DeliveryDedupCache
from connectors.linear.connector import LinearConnector

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "webhook_signed.json"


def _vec():
    fx = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    body = json.dumps(fx["body"]).encode("utf-8")
    return fx, body


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _connector(fx, **kw) -> LinearConnector:
    ts_ms = fx["body"]["webhookTimestamp"]
    return LinearConnector(secret=fx["secret"], clock=lambda: ts_ms / 1000.0, **kw)


def _headers(fx, body) -> dict[str, str]:
    return {"Linear-Signature": _sign(fx["secret"], body)}


def test_verify_true_for_valid_signature():
    fx, body = _vec()
    assert _connector(fx).verify(headers=_headers(fx, body), body=body) is True


def test_verify_false_for_tampered_body():
    fx, body = _vec()
    assert _connector(fx).verify(headers=_headers(fx, body), body=body + b" ") is False


def test_verify_false_for_wrong_secret():
    fx, body = _vec()
    headers = {"Linear-Signature": _sign("other-secret", body)}
    assert _connector(fx).verify(headers=headers, body=body) is False


def test_verify_false_for_missing_signature_header():
    fx, body = _vec()
    assert _connector(fx).verify(headers={}, body=body) is False


def test_verify_false_for_malformed_json_body():
    fx, _ = _vec()
    bad = b"not json at all"
    headers = {"Linear-Signature": _sign(fx["secret"], bad)}  # valid sig over the bad body
    # HMAC passes, but the body won't parse -> fail closed, no raise.
    assert _connector(fx).verify(headers=headers, body=bad) is False


def test_verify_false_for_stale_timestamp():
    fx, body = _vec()
    ts_ms = fx["body"]["webhookTimestamp"]
    conn = LinearConnector(secret=fx["secret"], clock=lambda: (ts_ms / 1000.0) + 120)  # +2 min
    assert conn.verify(headers=_headers(fx, body), body=body) is False


def test_normalize_event_parses_after_verify():
    fx, body = _vec()
    out = _connector(fx).normalize_event(headers=_headers(fx, body), body=body)
    assert len(out) == 1
    assert out[0].source_ref.source_id == "linear"
    assert out[0].title.startswith("PLAT-318")


def test_normalize_event_rejects_unverified():
    fx, body = _vec()
    assert _connector(fx).normalize_event(headers=_headers(fx, body), body=body + b"!") == []


def test_normalize_event_empty_id_returns_empty():
    fx, _ = _vec()
    payload = dict(fx["body"])
    payload["webhookId"] = ""
    body = json.dumps(payload).encode("utf-8")
    conn = _connector(fx, dedup=DeliveryDedupCache())
    assert conn.normalize_event(headers=_headers(fx, body), body=body) == []


def test_normalize_event_dedup_second_delivery_returns_empty():
    fx, body = _vec()
    conn = _connector(fx, dedup=DeliveryDedupCache())
    headers = _headers(fx, body)
    assert len(conn.normalize_event(headers=headers, body=body)) == 1
    assert conn.normalize_event(headers=headers, body=body) == []
