# SPDX-License-Identifier: MIT
"""Universal ingest conformance tests across every acquisition method class."""

from __future__ import annotations

import pytest

from adapter.core.capabilities import SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from runtime.ingest_conformance import trace_ingest


@pytest.mark.parametrize(
    ("mode", "delivery_mode", "verification"),
    [
        (SourceMode.WEBHOOK, "webhook", "signed"),
        (SourceMode.ACTIVE, "poll", "unsigned"),
        (SourceMode.PASSIVE, "active-fetch", "unsigned"),
        (SourceMode.DISCOVERY, "poll", "unsigned"),
    ],
)
def test_all_ingest_method_classes_use_universal_pipeline(
    mode: SourceMode,
    delivery_mode: str,
    verification: str,
) -> None:
    observation = Observation(
        source_ref=SourceRef(
            source_id="recorded_source",
            ref=f"recorded:{mode.value}:1",
            url="https://example.invalid/source/1",
            kind="recorded_item",
        ),
        excerpt="approved",
        title="Recorded source item",
        mode=mode,
        author="automation[bot]",
        timestamp="2026-07-17T05:00:00Z",
        provider_event_id=f"delivery:{mode.value}:1",
        provider_resource_id="item:1",
        evidence_id=f"evidence:{mode.value}:1",
        metadata={
            "actor_type": "Bot",
            "advisory_signals": [
                {
                    "code": "bot_authored",
                    "scope": "integration",
                    "basis": "recorded_provider_actor_type",
                    "confidence": "high",
                    "recommended_effect": "annotate",
                    "explanation": "The provider marked the author as automation.",
                    "schema_version": 1,
                }
            ],
        },
    )

    trace = trace_ingest([observation], adapter_version="recorded/1.0.0")[0]

    assert trace["observation"]["excerpt"] == "approved"
    assert trace["emission"]["evidence"][0]["excerpt"] == "approved"
    assert trace["emission"]["provenance"]["delivery_mode"] == delivery_mode
    assert trace["emission"]["provenance"]["verification"] == verification
    assert [item["code"] for item in trace["emission"]["advisories"]] == [
        "bot_authored",
        "status_only",
    ]
    labels = trace["external_ingest_envelope"]["candidate_hints"][0]["labels"]
    assert any(label.startswith("advisory_v1:bot_authored:integration:") for label in labels)
    assert any(label.startswith("advisory_v1:status_only:universal:") for label in labels)


def test_malformed_provider_heuristic_fails_open() -> None:
    observation = Observation(
        source_ref=SourceRef(source_id="recorded_source", ref="item:2"),
        excerpt="A meaningful architecture decision remains available.",
        metadata={"advisory_signals": "not-a-sequence"},
    )

    trace = trace_ingest([observation], adapter_version="recorded/1.0.0")[0]

    assert trace["emission"]["evidence"][0]["excerpt"] == observation.excerpt
    assert trace["emission"]["advisories"][0]["code"] == "heuristic_schema_error"


def test_heuristics_never_remove_or_rewrite_evidence() -> None:
    text = "<!-- issue template --> Keep this real decision despite noisy framing."
    observation = Observation(
        source_ref=SourceRef(source_id="recorded_source", ref="item:3"),
        excerpt=text,
        metadata={"actor_type": "Bot"},
    )

    trace = trace_ingest([observation], adapter_version="recorded/1.0.0")[0]

    assert trace["observation"]["excerpt"] == text
    assert trace["emission"]["body"] == text
    assert trace["external_ingest_envelope"]["content"] == text
