"""Behavior tests for the Fathom connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.fathom.connector import FathomConnector, parse_meeting

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "meeting_content_ready.json"


def _meeting() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads_as_dict():
    meeting = _meeting()
    assert isinstance(meeting, dict)
    for key in ("recording_id", "transcript", "meeting_title"):
        assert key in meeting


def test_parse_uses_meeting_title_and_recording_id():
    obs = parse_meeting(_meeting())
    assert obs.source_ref.source_id == "fathom"
    assert obs.source_ref.ref == "884412"
    assert obs.source_ref.kind == "meeting"
    assert obs.title == "Adopt feature-flag rollout for the connector cutover"


def test_parse_drops_speaker_names_keeps_text():
    # SG-2026-06-12-H: speaker.display_name (real name) is dropped; spoken text is kept.
    obs = parse_meeting(_meeting())
    assert "We will gate the connector cutover" in obs.excerpt
    assert "Agreed." in obs.excerpt
    assert "Dana Lee" not in obs.excerpt
    assert "Sam Rivera" not in obs.excerpt


def test_non_dict_default_summary_does_not_crash():
    # purple-team parse_robustness (medium): a truthy non-dict default_summary must floor, not crash.
    meeting = _meeting()
    meeting["transcript"] = []
    meeting["default_summary"] = "oops, a string not an object"
    obs = parse_meeting(meeting)  # must not raise
    assert obs.excerpt and obs.title  # floors to the title, no AttributeError


def test_transcript_redact_and_pass_scrubs_email():
    meeting = _meeting()
    meeting["transcript"] = [{"speaker": {"display_name": "Dana"}, "text": "ping me at dana@corp.com"}]
    obs = parse_meeting(meeting)
    assert "dana@corp.com" not in obs.excerpt  # redact-and-pass
    assert "Dana" not in obs.excerpt           # speaker name dropped


def test_parse_falls_back_to_summary_then_title():
    meeting = _meeting()
    meeting["transcript"] = []
    obs = parse_meeting(meeting)
    assert obs.excerpt.startswith("## Summary")
    meeting["default_summary"] = {}
    obs2 = parse_meeting(meeting)
    assert obs2.excerpt == meeting["meeting_title"]


def test_flatten_drops_speaker_emits_bare_text():
    # speaker (dict or bare string) is dropped; only spoken text is emitted.
    meeting = _meeting()
    meeting["transcript"] = [{"speaker": "Casey", "text": "Ship it."}]
    obs = parse_meeting(meeting)
    assert obs.excerpt == "Ship it."
    assert "Casey" not in obs.excerpt


def test_parse_drops_author_keeps_timestamp():
    obs = parse_meeting(_meeting())
    assert obs.author == ""  # recorded_by.name (real-name PII) dropped — SG-2026-06-11-D (deep-audit)
    assert obs.timestamp == "2026-06-02T15:28:42Z"


def test_end_to_end_normalizes_to_emission():
    meeting = _meeting()
    out = normalize(
        FathomConnector().observations(meeting), adapter_version="fathom/0.1.0"
    )
    assert len(out) == 1
    emission = out[0]
    assert isinstance(emission, AdapterEmission)
    assert emission.source_id == "fathom"
    assert emission.title == meeting["meeting_title"]
    assert emission.evidence[0].excerpt.strip()
