# SPDX-License-Identifier: MIT
"""Behavioral tests for NotionConnector webhook verify + dedup (X-Notion-Signature)."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from adapter.core.webhook_security import DeliveryDedupCache
from connectors.notion.connector import NotionConnector

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "webhook_page.json"
_SECRET = "notion-verification-token"


def _body() -> bytes:
    return json.dumps(json.loads(_FIXTURE.read_text(encoding="utf-8"))).encode("utf-8")


def _hex(body: bytes) -> str:
    return hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _headers(body: bytes) -> dict[str, str]:
    return {"X-Notion-Signature": "sha256=" + _hex(body)}


def test_verify_true_for_valid_signature():
    body = _body()
    assert NotionConnector(secret=_SECRET).verify(headers=_headers(body), body=body) is True


def test_verify_false_for_bare_hex_without_prefix():
    # Correct HMAC but missing the required sha256= prefix -> rejected (form pinned).
    body = _body()
    conn = NotionConnector(secret=_SECRET)
    assert conn.verify(headers={"X-Notion-Signature": _hex(body)}, body=body) is False


def test_verify_false_for_tampered_body():
    body = _body()
    assert NotionConnector(secret=_SECRET).verify(headers=_headers(body), body=body + b" ") is False


def test_verify_false_for_missing_header():
    body = _body()
    assert NotionConnector(secret=_SECRET).verify(headers={}, body=body) is False


def test_normalize_event_parses_after_verify():
    body = _body()
    out = NotionConnector(secret=_SECRET).normalize_event(headers=_headers(body), body=body)
    assert len(out) == 1 and out[0].source_ref.source_id == "notion"
    assert out[0].title == "Q3 Launch Plan"


def test_normalize_event_dedup_second_delivery_returns_empty():
    body = _body()
    conn = NotionConnector(secret=_SECRET, dedup=DeliveryDedupCache())
    assert len(conn.normalize_event(headers=_headers(body), body=body)) == 1
    assert conn.normalize_event(headers=_headers(body), body=body) == []
