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


def test_truthy_non_str_starting_at_does_not_crash():
    # purple-team ANTHROPIC-ADMIN-PARSE-1: a truthy non-str starting_at must normalize, not crash.
    obs = parse_usage({"starting_at": 12345, "results": []})  # must not raise
    assert obs.source_ref.ref == "anthropic-usage" and obs.excerpt


def test_pii_free_by_construction_opaque_dimensions_never_surfaced():
    # Descriptor PII-free claim: even a PII-shaped value in a non-surfaced grouping dimension
    # cannot leak — the connector reads only token metrics + model, never workspace/key ids.
    bucket = {"starting_at": "2026-06-04T00:00:00Z", "results": [
        {"model": "claude-opus-4-8", "workspace_id": "owner-jane@corp.com",
         "api_key_id": "apikey_secret", "output_tokens": 5, "uncached_input_tokens": 10}]}
    obs = parse_usage(bucket)
    assert "jane@corp.com" not in obs.excerpt
    assert "apikey_secret" not in obs.excerpt
    assert obs.author == ""  # no person attribution
    assert "10 input / 5 output" in obs.excerpt  # metrics still summarized
