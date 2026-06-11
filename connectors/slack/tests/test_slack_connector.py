# SPDX-License-Identifier: MIT
"""Behavior tests for the Slack connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.slack.connector import SlackConnector, parse_message

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "message_event.json"


def _event() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads():
    assert _event()["type"] == "event_callback"


def test_parse_unwraps_event_callback():
    obs = parse_message(_event())
    assert obs.excerpt.startswith("Decision: we will cut")
    assert obs.author == "U2147483697"


def test_parse_maps_text_author_ref():
    obs = parse_message(_event())
    assert obs.source_ref.source_id == "slack"
    assert "C12345" in obs.source_ref.ref and "1780000000.000200" in obs.source_ref.ref
    assert obs.timestamp == "1780000000.000200"
    assert obs.metadata["channel"] == "C12345"


def test_message_text_redacted_and_pass():
    # message text is free-text -> redact-and-pass scrubs an embedded email; non-PII text survives.
    obs = parse_message({"event": {"type": "message", "channel": "C1", "user": "U1",
                                   "text": "ship it, cc dave@corp.com", "ts": "1.2"}})
    assert "dave@corp.com" not in obs.excerpt
    assert "ship it" in obs.excerpt


def test_parse_accepts_bare_message():
    bare = _event()["event"]
    obs = parse_message(bare)
    assert obs.excerpt.startswith("Decision:")


def test_parse_message_falls_back_when_text_empty():
    obs = parse_message({"event": {"type": "message", "channel": "C9", "user": "U1", "text": "   ", "ts": "1.2"}})
    assert obs.excerpt.strip()  # non-blank → passes the evidence_excerpt_blank contract
    assert "C9:1.2" in obs.excerpt
    # and it actually normalizes (does not raise)
    out = normalize([obs], adapter_version="slack/0.1.0")
    assert out[0].source_id == "slack"


def test_parse_unwraps_edited_message_subtype():
    # message_changed carries the real content in a nested `message` object;
    # the connector must surface it rather than emit a "(no text)" placeholder.
    obs = parse_message(
        {
            "event": {
                "type": "message",
                "subtype": "message_changed",
                "channel": "C7",
                "ts": "9.9",
                "message": {"text": "real edited content", "user": "U9"},
            }
        }
    )
    assert obs.excerpt == "real edited content"
    assert obs.author == "U9"


def test_parse_uses_event_object_even_when_empty():
    # An event_callback whose `event` is present-but-empty must not leak the
    # envelope's own type/fields into the message metadata.
    obs = parse_message({"type": "event_callback", "channel": "CENV", "ts": "9", "event": {}})
    assert obs.metadata["type"] == ""
    assert obs.excerpt.strip()


def test_end_to_end_normalizes():
    out = normalize(SlackConnector().observations(_event()), adapter_version="slack/0.1.0")
    assert len(out) == 1
    assert isinstance(out[0], AdapterEmission) and out[0].source_id == "slack"
