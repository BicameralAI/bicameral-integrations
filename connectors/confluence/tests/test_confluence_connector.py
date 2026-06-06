# SPDX-License-Identifier: MIT
"""Unit tests for the Confluence connector parse surface (verify deferred)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from connectors.confluence.connector import _strip_storage_html, parse_content

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_content_extracts_storage_text():
    obs = parse_content(_load("page_content.json"))
    assert "We will adopt Postgres" in obs.excerpt  # storage text survives
    assert "<p>" not in obs.excerpt and "<h1>" not in obs.excerpt  # tags stripped
    assert "&" in obs.excerpt and "&amp;" not in obs.excerpt  # entity unescaped
    assert obs.source_ref.kind == "page"
    assert obs.source_ref.ref == "327681"
    # non-vacuous full joined URL (base + webui), advisory [grounding][LOW]
    assert obs.source_ref.url == (
        "https://example.atlassian.net/wiki/spaces/ENG/pages/327681/"
        "Event+Store+Substrate+Decision"
    )


def test_strip_storage_html_removes_tags_and_unescapes():
    assert _strip_storage_html("<p>A &amp; B</p>") == "A & B"
    assert _strip_storage_html("<h2>Heading</h2><p>Body  text</p>") == "Heading Body text"


def test_strip_storage_html_handles_unclosed_tag_runs_quickly():
    payload = "<" * 100_000
    start = time.perf_counter()

    assert _strip_storage_html(payload) == payload

    elapsed = time.perf_counter() - start
    assert elapsed < 0.5


def test_blank_body_floors_to_title_then_literal():
    # empty storage -> excerpt falls back to title
    only_title = {"title": "Decision Record", "body": {"storage": {"value": ""}}}
    assert parse_content(only_title).excerpt == "Decision Record"
    # empty title AND body -> terminal floor
    empty = {"title": "", "body": {"storage": {"value": "   "}}}
    obs = parse_content(empty)
    assert obs.excerpt == "confluence-page"
    assert obs.source_ref.ref == "confluence-page"
