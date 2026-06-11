# SPDX-License-Identifier: MIT
"""Behavioral tests for NotionConnector webhook verify + dedup (X-Notion-Signature)."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from adapter.core.webhook_security import DeliveryDedupCache
from connectors.notion.connector import NotionConnector

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "webhook_event.json"
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


def test_normalize_event_keys_ref_on_entity_id_not_event_id():
    # deep-audit HIGH: the Observation ref must be the page entity.id (the stable subject),
    # NOT the ephemeral top-level event id, so evidence ties to the page that changed.
    body = _body()
    out = NotionConnector(secret=_SECRET).normalize_event(headers=_headers(body), body=body)
    assert len(out) == 1 and out[0].source_ref.source_id == "notion"
    assert out[0].source_ref.ref == "page-abc-123"             # entity.id (subject)
    assert out[0].source_ref.ref != "evt-7c2a-delivery-0001"   # NOT the event id
    assert out[0].title == "Notion page.content_updated"       # pointer, not a fabricated page title
    assert "page-abc-123" in out[0].excerpt


def test_two_events_over_one_page_correlate_by_subject():
    # Distinct event ids on the same page yield the SAME ref (entity.id) -> correlate by subject,
    # and are NOT deduped (they are distinct changes, not replays).
    conn = NotionConnector(secret=_SECRET, dedup=DeliveryDedupCache())
    e1 = {"id": "evt-A", "type": "page.content_updated", "entity": {"id": "page-X", "type": "page"}}
    e2 = {"id": "evt-B", "type": "page.locked", "entity": {"id": "page-X", "type": "page"}}
    b1, b2 = json.dumps(e1).encode(), json.dumps(e2).encode()
    o1 = conn.normalize_event(headers=_headers(b1), body=b1)
    o2 = conn.normalize_event(headers=_headers(b2), body=b2)
    assert o1[0].source_ref.ref == o2[0].source_ref.ref == "page-X"  # same subject
    assert len(o1) == 1 and len(o2) == 1  # distinct events, not deduped


def test_normalize_event_dedup_second_delivery_returns_empty():
    body = _body()
    conn = NotionConnector(secret=_SECRET, dedup=DeliveryDedupCache())
    assert len(conn.normalize_event(headers=_headers(body), body=body)) == 1
    assert conn.normalize_event(headers=_headers(body), body=body) == []


def test_idless_signed_body_replay_deduped_by_body_hash():
    # A signed body with no derivable event id must still dedup on replay (body-hash fallback),
    # not bypass dedup unbounded (deep-audit medium).
    conn = NotionConnector(secret=_SECRET, dedup=DeliveryDedupCache())
    payload = {"type": "page.content_updated", "entity": {"id": "page-Y", "type": "page"}}  # no id
    body = json.dumps(payload).encode()
    assert len(conn.normalize_event(headers=_headers(body), body=body)) == 1
    assert conn.normalize_event(headers=_headers(body), body=body) == []  # replay collapsed
