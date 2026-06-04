# SPDX-License-Identifier: MIT
"""Behavior tests for the Continue connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.continue_dev.connector import ContinueConnector, parse_event

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "dev_data_event.json"


def _event() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads():
    assert _event()["name"] == "chatInteraction"


def test_parse_maps_prompt_and_event_name():
    obs = parse_event(_event())
    assert obs.excerpt.startswith("Refactor the retry helper")
    assert obs.title == "chatInteraction"
    assert obs.source_ref.kind == "chatInteraction"
    assert obs.metadata["model"] == "Claude (Opus)"
    assert obs.metadata["schema"] == "0.2.0"
    assert obs.source_ref.ref == "evt-7f3a9c21"
    assert obs.timestamp == "2026-06-03T15:04:22.000Z"


def test_excerpt_falls_back_to_completion_then_event_name():
    no_prompt = {"name": "editOutcome", "completion": "applied 3-line edit"}
    assert parse_event(no_prompt).excerpt == "applied 3-line edit"
    no_text = {"name": "editOutcome"}
    assert parse_event(no_text).excerpt == "continue editOutcome"


def test_floors_excerpt_when_empty():
    # No name and no text field → terminal literals keep excerpt + ref non-blank.
    obs = parse_event({})
    assert obs.excerpt == "continue continue-event"
    assert obs.source_ref.ref.startswith("continue-event")
    out = normalize([obs], adapter_version="continue/0.1.0")
    assert out[0].evidence[0].excerpt.strip()


def test_non_string_fields_do_not_crash():
    # A version-skewed event with non-string fields normalizes, not crashes.
    obs = parse_event({"name": 7, "prompt": 123, "completion": ["x"], "eventId": 99})
    assert obs.excerpt == "continue 7"
    assert obs.source_ref.ref == "99"
    out = normalize([obs], adapter_version="continue/0.1.0")
    assert out[0].source_id == "continue" and out[0].evidence[0].excerpt.strip()


def test_end_to_end_normalizes():
    out = normalize(
        ContinueConnector().observations(_event()), adapter_version="continue/0.1.0"
    )
    assert len(out) == 1
    assert isinstance(out[0], AdapterEmission) and out[0].source_id == "continue"
