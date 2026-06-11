# SPDX-License-Identifier: MIT
"""Behavior tests for the Notion connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.notion.connector import NotionConnector, parse_page

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "page.json"


def _page() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads():
    assert _page()["object"] == "page"


def test_parse_extracts_title_from_title_property():
    obs = parse_page(_page())
    assert obs.title == "Adopt Postgres event store"
    assert obs.excerpt == "Adopt Postgres event store"


def test_title_redacted_and_pass():
    # the page title is free-text -> redact-and-pass scrubs an embedded email; non-PII text survives.
    page = _page()
    page["properties"] = {"Name": {"type": "title", "title": [{"plain_text": "Sync with sam@corp.com re: launch"}]}}
    obs = parse_page(page)
    assert "sam@corp.com" not in obs.title
    assert "re: launch" in obs.title


def test_parse_falls_back_to_id_when_untitled():
    page = _page()
    page["properties"] = {}
    obs = parse_page(page)
    assert obs.excerpt == page["id"]


def test_parse_floors_excerpt_when_no_id_and_untitled():
    # Untitled page with no usable id (partial object / webhook envelope) must
    # still yield a non-blank excerpt and normalize without raising.
    obs = parse_page({})
    assert obs.excerpt == "notion-page"
    out = normalize([obs], adapter_version="notion/0.1.0")
    assert out[0].evidence[0].excerpt.strip()


def test_parse_sets_ref_url_timestamp():
    obs = parse_page(_page())
    assert obs.source_ref.source_id == "notion"
    assert obs.source_ref.ref == _page()["id"]
    assert obs.source_ref.url.startswith("https://www.notion.so/")
    assert obs.author == "u-9f3a"
    assert obs.timestamp == "2026-06-03T14:30:00.000Z"


def test_end_to_end_normalizes():
    out = normalize(NotionConnector().observations(_page()), adapter_version="notion/0.1.0")
    assert len(out) == 1
    assert isinstance(out[0], AdapterEmission) and out[0].source_id == "notion"
