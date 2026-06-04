"""Behavioral tests for FathomConnector webhook verify + dedup (Svix)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path

from adapter.core.webhook_security import DeliveryDedupCache
from connectors.fathom.connector import FathomConnector

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "webhook_signed.json"


def _vec():
    fx = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    body = json.dumps(fx["body"]).encode("utf-8")
    return fx, body


def _sign(secret: str, wid: str, ts: int, body: bytes) -> str:
    key = base64.b64decode(secret[len("whsec_") :])
    signed = wid.encode() + b"." + str(ts).encode() + b"." + body
    return "v1," + base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()


def _headers(fx, body) -> dict[str, str]:
    return {
        "webhook-id": fx["webhook_id"],
        "webhook-timestamp": str(fx["webhook_timestamp"]),
        "webhook-signature": _sign(fx["secret"], fx["webhook_id"], fx["webhook_timestamp"], body),
    }


def _connector(fx, **kw) -> FathomConnector:
    return FathomConnector(secret=fx["secret"], clock=lambda: float(fx["webhook_timestamp"]), **kw)


def test_verify_true_for_valid_signature():
    fx, body = _vec()
    assert _connector(fx).verify(headers=_headers(fx, body), body=body) is True


def test_verify_false_for_tampered_body():
    fx, body = _vec()
    assert _connector(fx).verify(headers=_headers(fx, body), body=body + b" ") is False


def test_verify_false_for_missing_secret():
    fx, body = _vec()
    conn = FathomConnector(secret="", clock=lambda: float(fx["webhook_timestamp"]))
    assert conn.verify(headers=_headers(fx, body), body=body) is False


def test_normalize_event_parses_after_verify():
    fx, body = _vec()
    out = _connector(fx).normalize_event(headers=_headers(fx, body), body=body)
    assert len(out) == 1
    assert out[0].source_ref.source_id == "fathom"
    assert "retention" in out[0].title


def test_normalize_event_rejects_unverified():
    fx, body = _vec()
    # Tampered body fails the self-guard -> [].
    assert _connector(fx).normalize_event(headers=_headers(fx, body), body=body + b"!") == []


def test_normalize_event_empty_id_returns_empty():
    fx, body = _vec()
    headers = _headers(fx, body)
    headers["webhook-id"] = ""  # valid sig is over empty id below
    headers["webhook-signature"] = _sign(fx["secret"], "", fx["webhook_timestamp"], body)
    conn = _connector(fx, dedup=DeliveryDedupCache())
    assert conn.normalize_event(headers=headers, body=body) == []


def test_normalize_event_dedup_second_delivery_returns_empty():
    fx, body = _vec()
    conn = _connector(fx, dedup=DeliveryDedupCache())
    headers = _headers(fx, body)
    assert len(conn.normalize_event(headers=headers, body=body)) == 1
    assert conn.normalize_event(headers=headers, body=body) == []
