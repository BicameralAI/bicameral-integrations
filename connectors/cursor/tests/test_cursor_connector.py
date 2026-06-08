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
    assert obs.source_ref.ref == "cursor:usage:2026-06-04:user:4471"
    assert "+210 accepted lines" in obs.excerpt
    assert "34/40 accepts" in obs.excerpt
    assert "18 agent + 22 chat + 12 composer requests" in obs.excerpt
    assert "model claude-4-sonnet" in obs.excerpt


def test_pii_is_dropped():
    # The fixture CONTAINS email + name (non-vacuous): they must appear NOWHERE.
    # (Per SG-2026-06-05-D the OPAQUE userId IS now surfaced for attribution; email/name are not.)
    # NOTE: `name` is NOT a real daily-usage-data field (verified 2026-06-08 — it lives on the
    # members/spend endpoints); it is kept here as a hostile-SUPERSET probe proving the never-read
    # allowlist drops an unexpected identity field even if a future/wrong payload includes it.
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
    assert "@" not in haystack  # no email artifact at all (identity never read)


def test_user_attribution_surfaces_opaque_userid():
    # SG-2026-06-05-D: the opaque vendor userId is surfaced for per-developer attribution.
    obs = parse_usage_day(_load("daily_usage_row.json"))
    assert obs.source_ref.ref.endswith(":user:4471")
    assert "user 4471" in obs.excerpt


def test_blank_day_floors():
    obs = parse_usage_day({"acceptedLinesAdded": 3})
    assert obs.source_ref.ref == "cursor-usage"
    assert obs.excerpt.startswith("Cursor usage usage:")  # day floored in summary
    assert obs.title == "Cursor usage"


def test_freetext_day_and_model_redacted():
    # #58: day/mostUsedModel are free-text -> redacted; opaque userId preserved.
    obs = parse_usage_day({"userId": 42, "day": "x@evil.com", "mostUsedModel": "a@b.com",
                           "acceptedLinesAdded": 3})
    blob = obs.excerpt + obs.title + obs.source_ref.ref
    assert "@" not in blob  # email scrubbed from day + model
    assert "user 42" in obs.excerpt  # opaque userId attribution preserved
