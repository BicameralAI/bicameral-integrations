"""Behavior tests for the Granola connector and end-to-end normalization.

Verified shape (public-api.granola.ai, 2026-06-11): note `id` (not_ prefix), `title`, `owner`
{name,email}, embedded `transcript` of {speaker:{source,diarization_label}, text}, `created_at`.
PII contract (SG-2026-06-11-D): transcript + title redact-and-passed; owner identity dropped.
"""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.granola.connector import GranolaConnector, parse_transcript

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "transcript.json"

_TITLE = "Design review: source-trust gating"
_NON_PII_SPEECH = "low-trust sources route to review, never auto-block"
_TRANSCRIPT_EMAIL = "marco.diaz@example.com"
_OWNER_EMAIL = "priya.anand@example.com"
_OWNER_NAME = "Priya Anand"


def _item() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads_as_dict():
    item = _item()
    assert isinstance(item, dict)
    assert isinstance(item["transcript"], list)


def test_parse_redacts_transcript_pii():
    # The transcript is redact-and-passed: a spoken email is scrubbed, non-PII text survives.
    obs = parse_transcript(_item())
    assert _NON_PII_SPEECH in obs.excerpt
    assert _TRANSCRIPT_EMAIL not in obs.excerpt


def test_parse_drops_owner_identity():
    # The meeting owner's name/email is NEVER surfaced (author dropped, not in any wire field).
    obs = parse_transcript(_item())
    assert obs.author == ""
    for field in (obs.excerpt, obs.title):
        assert _OWNER_NAME not in field
        assert _OWNER_EMAIL not in field


def test_parse_ref_and_timestamp():
    obs = parse_transcript(_item())
    assert obs.source_ref.source_id == "granola"
    assert obs.source_ref.ref == "not_5521abcdEFGijk"
    assert obs.timestamp == "2026-06-01T21:14:00Z"


def test_parse_falls_back_to_title_when_text_empty():
    item = _item()
    item["transcript"] = []
    obs = parse_transcript(item)
    assert obs.excerpt == _TITLE  # redacted title (no PII in title) is the fallback


def test_end_to_end_normalizes_to_emission_without_raw_pii():
    out = normalize(GranolaConnector().observations(_item()), adapter_version="granola/0.1.0")
    assert len(out) == 1
    assert isinstance(out[0], AdapterEmission)
    assert out[0].source_id == "granola"
    excerpt = out[0].evidence[0].excerpt
    assert _NON_PII_SPEECH in excerpt
    assert _TRANSCRIPT_EMAIL not in excerpt and _OWNER_EMAIL not in excerpt
