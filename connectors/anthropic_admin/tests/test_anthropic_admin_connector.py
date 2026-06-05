# SPDX-License-Identifier: MIT
"""Unit tests for the Anthropic Admin connector (usage buckets; aggregate, PII-free)."""

from __future__ import annotations

import json
from pathlib import Path

from connectors.anthropic_admin.connector import parse_usage

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_usage_summarizes_tokens():
    obs = parse_usage(_load("usage_bucket.json"))
    assert obs.source_ref.ref == "anthropic:usage:2026-06-04T00:00:00Z"
    assert obs.source_ref.kind == "usage_metrics"
    # input = (120000+30000+5000) + 60000 = 215000 ; output = 42000+18000 = 60000
    assert "215000 input / 60000 output tokens" in obs.excerpt
    assert "across 2 group(s)" in obs.excerpt
    assert "claude-opus-4-8" in obs.excerpt and "claude-sonnet-4-6" in obs.excerpt
    # opaque ids are NOT surfaced
    assert "wrkspc_" not in obs.excerpt and "apikey_" not in obs.excerpt


def test_missing_results_floor():
    obs = parse_usage({"starting_at": "2026-06-04T00:00:00Z"})
    assert "0 input / 0 output tokens across 0 group(s)" in obs.excerpt  # non-blank, no crash


def test_blank_bucket_floors():
    obs = parse_usage({})
    assert obs.source_ref.ref == "anthropic-usage"
    assert obs.excerpt  # non-blank
