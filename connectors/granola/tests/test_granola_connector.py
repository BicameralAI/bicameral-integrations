"""Behavior tests for the Granola connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.granola.connector import GranolaConnector, parse_transcript

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "transcript.json"


def _item() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads_as_dict():
    item = _item()
    assert isinstance(item, dict)
    assert "transcript_text" in item


def test_parse_uses_transcript_text_as_excerpt():
    obs = parse_transcript(_item())
    assert obs.excerpt == _item()["transcript_text"]
    assert obs.title == "Design review: source-trust gating"


def test_parse_sets_ref_author_timestamp():
    obs = parse_transcript(_item())
    assert obs.source_ref.source_id == "granola"
    assert obs.source_ref.ref == "gr_5521"
    assert obs.author == "Priya Anand"
    assert obs.timestamp == "2026-06-01T21:14:00Z"


def test_parse_falls_back_to_title_when_text_empty():
    item = _item()
    item["transcript_text"] = ""
    obs = parse_transcript(item)
    assert obs.excerpt == item["title"]


def test_end_to_end_normalizes_to_emission():
    item = _item()
    out = normalize(
        GranolaConnector().observations(item), adapter_version="granola/0.1.0"
    )
    assert len(out) == 1
    assert isinstance(out[0], AdapterEmission)
    assert out[0].source_id == "granola"
    assert out[0].evidence[0].excerpt == item["transcript_text"]
