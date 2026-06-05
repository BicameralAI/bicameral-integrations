# SPDX-License-Identifier: MIT
"""Unit tests for the Devin connector (session parse surface + redaction)."""

from __future__ import annotations

import json
from pathlib import Path

from connectors.devin.connector import parse_session

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_session_maps_metadata():
    obs = parse_session(_load("session.json"))
    assert obs.source_ref.ref == "devin-abc123def456"
    assert obs.source_ref.kind == "session"
    assert obs.source_ref.url == "https://github.com/acme/widgets/pull/42"  # artifact location kept
    assert "[finished]" in obs.excerpt
    assert "Add OAuth login" in obs.excerpt


def test_session_body_is_redacted():
    obs = parse_session(_load("session.json"))
    assert "[redacted:email]" in obs.excerpt and "[redacted:phone]" in obs.excerpt
    assert "jane.doe@example.com" not in obs.excerpt
    assert "555-0132" not in obs.excerpt
    assert "@" not in obs.excerpt


def test_blank_session_floors():
    obs = parse_session({})
    assert obs.source_ref.ref == "devin-session"
    assert obs.excerpt == "devin-session"  # floored, non-blank
