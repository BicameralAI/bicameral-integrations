# SPDX-License-Identifier: MIT
"""Tests for generated data-bearing lifecycle Markdown pages."""

from __future__ import annotations

import pytest

from adapter.core.capabilities import SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from runtime.ingest_conformance import trace_ingest
from runtime.ingest_lifecycle_markdown import render_markdown_trace


def _trace() -> dict:
    text = "Decision: preserve evidence and rank downstream."
    observation = Observation(
        source_ref=SourceRef(
            source_id="github",
            ref="BicameralAI/example#issues/7:comment:9",
            url="https://github.com/BicameralAI/example/issues/7#issuecomment-9",
            kind="issue_comment",
        ),
        excerpt=text,
        title="Incremental ingest",
        mode=SourceMode.WEBHOOK,
        author="automation[bot]",
        timestamp="2026-07-17T05:00:00Z",
        provider_event_id="delivery-9",
        provider_resource_id="issue_comment:9",
        evidence_id="github:comment:9:v1",
        metadata={"actor_type": "Bot"},
    )
    return trace_ingest(
        [observation],
        adapter_version="github/0.1.0",
        source_capture={
            "action": "created",
            "repository": {"full_name": "BicameralAI/example"},
            "issue": {"number": 7},
            "comment": {"body": text},
        },
        delivery_result={
            "status": 201,
            "cursor_verdict": "advance",
            "cursor": {"last_provider_event_id": "delivery-9"},
        },
    )[0]


def test_markdown_contains_mermaid_actual_data_and_all_phases() -> None:
    page = render_markdown_trace(_trace(), title="GitHub Issue Comment Lifecycle")

    assert page.startswith("# GitHub Issue Comment Lifecycle")
    assert "```mermaid\nflowchart LR" in page
    assert "Decision: preserve evidence and rank downstream." in page
    assert "## 1. Sanitized provider capture" in page
    assert "## 2. Provider-neutral Observation" in page
    assert "## 3. Validated AdapterEmission" in page
    assert "## 4. ExternalIngestEnvelope" in page
    assert "## 5. Gateway delivery and connector state" in page
    assert "### Preserved" in page
    assert "### Added" in page
    assert "### Removed" in page
    assert "evidence metadata and evidence_id" in page
    assert "terminal Bot persistence" in page


def test_markdown_serializes_phase_data_as_json() -> None:
    page = render_markdown_trace(_trace(), title="Lifecycle")

    assert '"source_id": "github"' in page
    assert '"status": 201' in page
    assert '"cursor_verdict": "advance"' in page


def test_markdown_rejects_missing_phases() -> None:
    with pytest.raises(ValueError, match="trace_has_no_phases"):
        render_markdown_trace({}, title="Invalid")


def test_markdown_rejects_invalid_phase() -> None:
    with pytest.raises(ValueError, match="trace_phase_invalid"):
        render_markdown_trace({"phases": ["invalid"]}, title="Invalid")


def test_markdown_rejects_invalid_transformation() -> None:
    trace = {
        "phases": [
            {
                "title": "Bad",
                "function": "bad",
                "data": {},
                "transformation": "invalid",
            }
        ]
    }
    with pytest.raises(ValueError, match="trace_transformation_invalid"):
        render_markdown_trace(trace, title="Invalid")
