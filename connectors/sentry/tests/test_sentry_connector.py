# SPDX-License-Identifier: MIT
"""Behavior tests for the Sentry connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.sentry.connector import SentryConnector, parse_issue

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "issue_event.json"


def _event() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads():
    assert _event()["action"] == "created"


def test_parse_unwraps_data_issue():
    obs = parse_issue(_event())
    assert obs.excerpt.startswith("TypeError: NoneType")
    assert obs.source_ref.source_id == "sentry"
    assert obs.source_ref.ref == "4571234567"
    assert obs.source_ref.url.endswith("/issues/4571234567/")
    assert obs.timestamp == "2026-06-03T11:22:33.000000Z"
    assert obs.metadata["action"] == "created"
    assert obs.metadata["level"] == "error"
    assert obs.metadata["short_id"] == "EXAMPLE-PROJECT-7Q"


def test_excerpt_falls_back_culprit_then_short_then_id():
    assert parse_issue({"data": {"issue": {"id": "1", "culprit": "mod.fn"}}}).excerpt == "mod.fn"
    assert parse_issue({"data": {"issue": {"id": "1", "shortId": "P-9"}}}).excerpt == "P-9"


def test_accepts_bare_issue_object():
    obs = parse_issue({"id": "9", "title": "boom"})
    assert obs.excerpt == "boom" and obs.source_ref.ref == "9"


def test_floors_excerpt_when_empty():
    obs = parse_issue({})
    assert obs.excerpt == "sentry-issue" and obs.source_ref.ref == "sentry-issue"
    out = normalize([obs], adapter_version="sentry/0.1.0")
    assert out[0].evidence[0].excerpt.strip()


def test_wrong_typed_title_culprit_do_not_crash():
    # Non-string title/culprit (a truthy int/list) must not crash on .strip().
    obs = parse_issue({"data": {"issue": {"id": "1", "title": 7, "culprit": ["x"]}}})
    assert obs.excerpt == "1"  # falls through to id floor
    out = normalize([obs], adapter_version="sentry/0.1.0")
    assert out[0].source_id == "sentry" and out[0].evidence[0].excerpt.strip()


def test_end_to_end_normalizes():
    out = normalize(SentryConnector().observations(_event()), adapter_version="sentry/0.1.0")
    assert len(out) == 1
    assert isinstance(out[0], AdapterEmission) and out[0].source_id == "sentry"
