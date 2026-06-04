"""Behavior tests for the local-directory connector and normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.local_directory.connector import (
    LocalDirectoryConnector,
    parse_file,
)

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "note.json"


def _payload() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads_as_dict():
    payload = _payload()
    assert isinstance(payload, dict)
    for key in ("path", "content", "modified"):
        assert key in payload


def test_parse_uses_content_as_excerpt():
    obs = parse_file(_payload())
    assert obs.excerpt == _payload()["content"]
    assert obs.source_ref.source_id == "local_directory"


def test_parse_derives_stem_title_and_token_ref():
    obs = parse_file(_payload())
    assert obs.title == "2026-06-01-event-store"
    assert obs.source_ref.ref.startswith("local-")
    # Deterministic: same path -> same token.
    assert parse_file(_payload()).source_ref.ref == obs.source_ref.ref


def test_parse_falls_back_to_stem_when_content_empty():
    payload = _payload()
    payload["content"] = ""
    obs = parse_file(payload)
    assert obs.excerpt == "2026-06-01-event-store"


def test_end_to_end_normalizes_to_emission():
    payload = _payload()
    out = normalize(
        LocalDirectoryConnector().observations(payload),
        adapter_version="local_directory/0.1.0",
    )
    assert len(out) == 1
    assert isinstance(out[0], AdapterEmission)
    assert out[0].source_id == "local_directory"
    assert out[0].evidence[0].excerpt == payload["content"]
