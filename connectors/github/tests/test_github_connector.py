"""Behavior tests for the GitHub PR connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.github.connector import GitHubConnector, parse_pull_request

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "pr_merged.json"


def _payload() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads_as_dict():
    payload = _payload()
    assert isinstance(payload, dict)
    for key in ("title", "body", "html_url", "user"):
        assert key in payload


def test_parse_extracts_source_ref():
    payload = _payload()
    obs = parse_pull_request(payload)
    assert obs.source_ref.source_id == "github"
    assert "BicameralAI/bicameral-bot" in obs.source_ref.ref
    assert "92" in obs.source_ref.ref
    assert obs.source_ref.url == payload["html_url"]


def test_parse_uses_body_as_excerpt():
    payload = _payload()
    obs = parse_pull_request(payload)
    assert obs.excerpt == payload["body"]
    assert obs.title == payload["title"]
    assert obs.author == payload["user"]["login"]


def test_parse_falls_back_to_title_when_body_empty():
    payload = _payload()
    payload["body"] = ""
    obs = parse_pull_request(payload)
    assert obs.excerpt == payload["title"]


def test_end_to_end_normalizes_to_emission():
    payload = _payload()
    out = normalize(
        GitHubConnector().observations(payload), adapter_version="github/0.1.0"
    )
    assert len(out) == 1
    emission = out[0]
    assert isinstance(emission, AdapterEmission)
    assert emission.source_id == "github"
    assert emission.title == payload["title"]
    assert emission.evidence[0].excerpt == payload["body"]
