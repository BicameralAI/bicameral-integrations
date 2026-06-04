"""Behavior tests for the Google Drive connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.google_drive.connector import (
    GoogleDriveConnector,
    extract_document_text,
    parse_document,
    parse_gdrive_url,
)

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "doc_decision.json"


def _document() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads_as_dict():
    document = _document()
    assert isinstance(document, dict)
    for key in ("documentId", "title", "body"):
        assert key in document


@pytest.mark.parametrize(
    "url",
    [
        "https://docs.google.com/document/d/1AbcDEFghIJKlmNOpqRStuVWxyz0123456789/edit",
        "https://docs.google.com/document/d/1AbcDEFghIJKlmNOpqRStuVWxyz0123456789",
        "https://drive.google.com/file/d/1AbcDEFghIJKlmNOpqRStuVWxyz0123456789/view",
    ],
)
def test_parse_gdrive_url_extracts_id(url):
    assert parse_gdrive_url(url) == "1AbcDEFghIJKlmNOpqRStuVWxyz0123456789"


def test_parse_gdrive_url_rejects_non_gdrive_url():
    with pytest.raises(ValueError):
        parse_gdrive_url("https://example.com/document/d/whatever")


def test_extract_document_text_walks_paragraphs_and_tables():
    text = extract_document_text(_document())
    assert text.startswith("# Event Store Substrate Decision")
    assert "We will adopt Postgres as the durable event store substrate." in text
    # Table cells are flattened in too — assert a table-EXCLUSIVE token so the
    # _walk_table path is actually covered (the paragraph text alone would
    # satisfy a bare "Postgres" check).
    assert "Option" in text


def test_parse_document_builds_observation():
    obs = parse_document(_document())
    assert obs.source_ref.source_id == "google_drive"
    assert obs.source_ref.ref.startswith("1AbcDEF")
    assert obs.title == "Event Store Substrate Decision"
    assert "Postgres" in obs.excerpt


def test_parse_document_falls_back_to_title_when_body_empty():
    obs = parse_document({"documentId": "x" * 25, "title": "Title Only", "body": {}})
    assert obs.excerpt == "Title Only"


def test_connector_can_handle_ref_by_url_and_source_id():
    from adapter.core.emissions import SourceRef

    connector = GoogleDriveConnector()
    assert connector.can_handle_ref(SourceRef(source_id="google_drive", ref="abc"))
    assert connector.can_handle_ref(
        SourceRef(
            source_id="",
            ref="",
            url="https://docs.google.com/document/d/1AbcDEFghIJKlmNOpqRStuVWxyz0123456789/edit",
        )
    )
    assert not connector.can_handle_ref(SourceRef(source_id="github", ref="o/r#1"))


def test_end_to_end_normalizes_to_emission():
    document = _document()
    out = normalize(
        GoogleDriveConnector().observations(document),
        adapter_version="google_drive/0.1.0",
    )
    assert len(out) == 1
    emission = out[0]
    assert isinstance(emission, AdapterEmission)
    assert emission.source_id == "google_drive"
    assert emission.title == document["title"]
    assert "Postgres" in emission.evidence[0].excerpt
