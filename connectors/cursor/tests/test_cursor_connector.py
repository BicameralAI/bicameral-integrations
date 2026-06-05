# SPDX-License-Identifier: MIT
"""Unit tests for the Cursor connector (PII-free daily-usage parse surface)."""

from __future__ import annotations

import json
from pathlib import Path

from connectors.cursor.connector import parse_usage_day

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_usage_day_summarizes_metrics():
    obs = parse_usage_day(_load("daily_usage_row.json"))
    assert obs.source_ref.kind == "usage_metrics"
    assert obs.source_ref.ref == "cursor:usage:2026-06-04"
    assert "+210 accepted lines" in obs.excerpt
    assert "34/40 accepts" in obs.excerpt
    assert "18 agent + 22 chat + 12 composer requests" in obs.excerpt
    assert "model claude-4-sonnet" in obs.excerpt


def test_pii_is_dropped():
    # The fixture CONTAINS email + name (non-vacuous): they must appear NOWHERE.
    row = _load("daily_usage_row.json")
    assert row["email"] == "jane.doe@example.com" and row["name"] == "Jane Doe"  # input has PII
    obs = parse_usage_day(row)
    haystack = " ".join(
        [
            obs.excerpt,
            obs.title,
            obs.author,
            obs.source_ref.ref,
            obs.source_ref.url,
            json.dumps(obs.metadata),
        ]
    )
    assert "jane.doe@example.com" not in haystack
    assert "Jane Doe" not in haystack
    assert "4471" not in haystack  # userId dropped too
    assert "@" not in haystack  # no email artifact at all


def test_blank_day_floors():
    obs = parse_usage_day({"acceptedLinesAdded": 3})
    assert obs.source_ref.ref == "cursor-usage"
    assert obs.excerpt.startswith("Cursor usage usage:")  # day floored in summary
    assert obs.title == "Cursor usage"
