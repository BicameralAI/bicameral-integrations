# SPDX-License-Identifier: MIT
"""Behavior tests for the Aider connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.aider.connector import AiderConnector, parse_commit

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "aider_commit.json"


def _commit() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads():
    assert _commit()["hash"].startswith("9c1e4f7a")


def test_parse_maps_subject_hash_author():
    obs = parse_commit(_commit())
    assert obs.excerpt == "aider: add exponential backoff to the retry helper"
    assert obs.title == obs.excerpt
    assert obs.source_ref.ref == _commit()["hash"]
    assert obs.source_ref.kind == "commit"
    assert obs.author == "Dev Example (aider)"
    assert obs.timestamp == "2026-06-03T15:06:10-04:00"
    assert obs.metadata["short_hash"] == "9c1e4f7"


def test_attributed_by_detects_author():
    assert parse_commit(_commit()).metadata["attributed_by"] == "author"


def test_attributed_by_detects_committer_only():
    rec = {"hash": "abc", "message": "x", "author_name": "Dev", "committer_name": "Dev (aider)"}
    assert parse_commit(rec).metadata["attributed_by"] == "committer"


def test_attributed_by_detects_co_author_trailer():
    rec = {
        "hash": "def",
        "message": "x",
        "author_name": "Dev",
        "trailers": [{"key": "Co-authored-by", "value": "aider (gpt) <noreply@aider.chat>"}],
    }
    assert parse_commit(rec).metadata["attributed_by"] == "co-author"


def test_attributed_by_handles_string_trailers():
    rec = {"hash": "g1", "message": "x", "trailers": ["Co-authored-by: aider <x@aider.chat>"]}
    assert parse_commit(rec).metadata["attributed_by"] == "co-author"


def test_floors_excerpt_when_empty():
    # No subject and no hash → terminal literal keeps excerpt + ref non-blank.
    obs = parse_commit({})
    assert obs.excerpt == "aider-commit"
    assert obs.source_ref.ref == "aider-commit"
    out = normalize([obs], adapter_version="aider/0.1.0")
    assert out[0].evidence[0].excerpt.strip()


def test_excerpt_floors_to_hash_when_message_blank():
    rec = {"hash": "feedface", "message": "   \n  "}
    assert parse_commit(rec).excerpt == "feedface"


def test_whitespace_hash_floors_to_literal():
    # A whitespace-only hash must not yield a whitespace excerpt/ref (it would
    # be blank after strip); the terminal literal applies.
    obs = parse_commit({"hash": "   ", "message": "  \n "})
    assert obs.excerpt == "aider-commit"
    assert obs.source_ref.ref == "aider-commit"
    out = normalize([obs], adapter_version="aider/0.1.0")
    assert out[0].evidence[0].excerpt.strip()


def test_non_string_fields_do_not_crash():
    # A malformed record with non-string fields normalizes, not crashes.
    obs = parse_commit({"hash": 12345, "message": 5, "author_name": 7, "committer_name": 9})
    assert obs.excerpt == "12345"
    assert obs.metadata["attributed_by"] == ""
    out = normalize([obs], adapter_version="aider/0.1.0")
    assert out[0].source_id == "aider" and out[0].evidence[0].excerpt.strip()


def test_end_to_end_normalizes():
    out = normalize(AiderConnector().observations(_commit()), adapter_version="aider/0.1.0")
    assert len(out) == 1
    assert isinstance(out[0], AdapterEmission) and out[0].source_id == "aider"
