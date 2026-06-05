# SPDX-License-Identifier: MIT
"""Unit tests for the GitHub Copilot connector (aggregate metrics parse surface)."""

from __future__ import annotations

import json
from pathlib import Path

from connectors.copilot.connector import parse_metrics_day

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_metrics_day_summarizes_aggregates():
    obs = parse_metrics_day(_load("metrics_day.json"))
    assert obs.source_ref.kind == "usage_metrics"
    assert obs.source_ref.ref == "copilot:metrics:2026-06-04"
    assert "120 active / 95 engaged users" in obs.excerpt
    assert "code-completions 88 engaged" in obs.excerpt  # breakdown summarized
    assert "PR summaries 12 engaged" in obs.excerpt
    assert obs.title == "Copilot usage metrics 2026-06-04"


def test_missing_breakdowns_do_not_crash():
    obs = parse_metrics_day({"date": "2026-06-04", "total_active_users": 5})
    assert obs.excerpt.startswith("Copilot 2026-06-04:")  # non-blank, no breakdown segments
    assert "5 active / ? engaged users" in obs.excerpt  # absent engaged -> '?'


def test_blank_date_floors():
    obs = parse_metrics_day({})
    assert obs.source_ref.ref == "copilot-metrics"
    assert obs.excerpt  # non-blank
    assert obs.title == "Copilot usage metrics"
