# SPDX-License-Identifier: MIT
"""Behavior tests for the PagerDuty connector and end-to-end normalization."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from adapter.core.webhook_security import DeliveryDedupCache
from connectors.pagerduty.connector import PagerDutyConnector, parse_event

_SECRET = "signing-secret"


def _sig(secret: str, body: bytes) -> str:
    return "v1=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _signed(payload: dict) -> tuple[dict, bytes]:
    body = json.dumps(payload).encode("utf-8")
    return {"X-PagerDuty-Signature": _sig(_SECRET, body)}, body

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "incident_event.json"


def _event() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads():
    assert _event()["event"]["event_type"] == "incident.triggered"


def test_parse_unwraps_event_data():
    obs = parse_event(_event())
    assert obs.excerpt == "Checkout latency p99 above SLO"
    assert obs.source_ref.source_id == "pagerduty"
    assert obs.source_ref.ref == "PINC123"
    assert obs.source_ref.url.endswith("/incidents/PINC123")
    assert obs.source_ref.kind == "incident"
    assert obs.timestamp == "2026-06-03T18:45:00Z"
    assert obs.metadata["event_type"] == "incident.triggered"
    assert obs.metadata["status"] == "triggered"
    assert obs.metadata["urgency"] == "high"


def test_excerpt_falls_back_summary_then_id():
    env = {"event": {"data": {"id": "P1", "summary": "DB down"}}}
    assert parse_event(env).excerpt == "DB down"
    assert parse_event({"event": {"data": {"id": "P1"}}}).excerpt == "P1"


def test_floors_excerpt_when_empty():
    obs = parse_event({})
    assert obs.excerpt == "pagerduty-incident" and obs.source_ref.ref == "pagerduty-incident"


def test_incident_title_redact_and_passed():
    # F1 (medium): an incident title carrying customer PII is redact-and-passed.
    env = {"event": {"data": {"id": "PINC1", "title": "High latency for jane@acme.com"}}}
    obs = parse_event(env)
    assert "jane@acme.com" not in obs.excerpt
    assert "jane@acme.com" not in obs.title
    assert "High latency" in obs.excerpt  # non-sensitive text preserved


def test_opaque_incident_id_floor_not_redacted():
    # The incident id floor is opaque — survives when title+summary are empty.
    obs = parse_event({"event": {"data": {"id": "PINC123"}}})
    assert obs.excerpt == "PINC123" and obs.source_ref.ref == "PINC123"
    out = normalize([obs], adapter_version="pagerduty/0.1.0")
    assert out[0].evidence[0].excerpt.strip()


def test_created_at_falls_back_to_occurred_at():
    env = {"event": {"occurred_at": "2026-06-03T00:00:00Z", "data": {"id": "P1", "title": "x"}}}
    assert parse_event(env).timestamp == "2026-06-03T00:00:00Z"


def test_wrong_typed_title_summary_do_not_crash():
    # Non-string title/summary (truthy int/list) must not crash on .strip().
    obs = parse_event({"event": {"data": {"id": "P1", "title": 7, "summary": ["x"]}}})
    assert obs.excerpt == "P1"  # falls through to id floor
    out = normalize([obs], adapter_version="pagerduty/0.1.0")
    assert out[0].source_id == "pagerduty" and out[0].evidence[0].excerpt.strip()


def test_end_to_end_normalizes():
    out = normalize(PagerDutyConnector().observations(_event()), adapter_version="pagerduty/0.1.0")
    assert len(out) == 1
    assert isinstance(out[0], AdapterEmission) and out[0].source_id == "pagerduty"


def test_verify_accepts_rotation_set_rejects_tampered():
    c = PagerDutyConnector(secret=_SECRET)
    headers, body = _signed(_event())
    assert c.verify(headers=headers, body=body) is True
    # rotation: stale digest under old secret + valid one -> accept
    rotated = {"X-PagerDuty-Signature": _sig("old", body) + "," + _sig(_SECRET, body)}
    assert c.verify(headers=rotated, body=body) is True
    assert c.verify(headers=headers, body=body + b" ") is False   # tampered body
    assert c.verify(headers={"X-PagerDuty-Signature": "v1="}, body=body) is False  # empty candidate
    assert c.verify(headers={}, body=body) is False               # missing header


def test_normalize_event_rejects_bad_sig_dedups_and_handles_wrong_typed_id():
    headers, body = _signed(_event())
    c = PagerDutyConnector(secret=_SECRET, dedup=DeliveryDedupCache())
    assert c.normalize_event(headers=headers, body=body)               # 1st parsed (event.id=01EXAMPLE0EVENT)
    assert c.normalize_event(headers=headers, body=body) == []         # deduped
    assert c.normalize_event(headers={"X-PagerDuty-Signature": "v1=bad"}, body=body) == []
    # wrong-typed event.id must not crash; best-effort dedup processes it
    p2 = {"event": {"id": 123, "data": {"id": "PX", "title": "x"}}}
    h2, b2 = _signed(p2)
    out = PagerDutyConnector(secret=_SECRET, dedup=DeliveryDedupCache()).normalize_event(headers=h2, body=b2)
    assert len(out) == 1 and out[0].source_ref.ref == "PX"
