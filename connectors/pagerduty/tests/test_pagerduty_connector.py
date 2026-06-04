# SPDX-License-Identifier: MIT
"""Behavior tests for the PagerDuty connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.pagerduty.connector import PagerDutyConnector, parse_event

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
