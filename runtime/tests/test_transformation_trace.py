# SPDX-License-Identifier: MIT
"""Tests for the canonical cross-repository transformation trace."""

from __future__ import annotations

from copy import deepcopy

import pytest

from adapter.core.capabilities import SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from runtime.ingest_conformance import trace_ingest
from runtime.transformation_trace import (
    TransformationTraceContext,
    TransformationTraceContractError,
    canonical_digest,
    project_ingest_transformation_trace,
    validate_transformation_trace_set,
)


def _legacy_trace() -> dict:
    observation = Observation(
        source_ref=SourceRef(
            source_id="github",
            ref="BicameralAI/example#issues/7:comment:9",
            url="https://github.com/BicameralAI/example/issues/7#issuecomment-9",
            kind="issue_comment",
        ),
        excerpt="Decision: preserve evidence and rank downstream.",
        title="Incremental ingest",
        mode=SourceMode.WEBHOOK,
        author="automation[bot]",
        timestamp="2026-07-17T05:00:00Z",
        provider_event_id="delivery-9",
        provider_resource_id="issue_comment:9",
        evidence_id="github:comment:9:v1",
        metadata={
            "actor_type": "Bot",
            "stale_source": True,
            "advisory_signals": [
                {
                    "code": "bot_authored",
                    "scope": "integration",
                    "basis": "github_actor_type",
                    "confidence": "high",
                    "recommended_effect": "annotate",
                    "explanation": "The provider marked the author as automation.",
                    "schema_version": 1,
                }
            ],
        },
    )
    return trace_ingest(
        [observation],
        adapter_version="github/0.1.0",
        source_capture={
            "action": "created",
            "repository": {"full_name": "BicameralAI/example"},
            "issue": {"number": 7},
            "comment": {"body": observation.excerpt},
        },
        delivery_result={
            "status": 201,
            "cursor_verdict": "advance",
            "cursor": {"last_provider_event_id": "delivery-9"},
        },
    )[0]


def _context() -> TransformationTraceContext:
    fingerprints = {
        "bicameral.provider-capture/v1": "sha256:" + "1" * 64,
        "bicameral.observation/v1": "sha256:" + "2" * 64,
        "bicameral.ingress-advisory/v1": "sha256:" + "3" * 64,
        "bicameral.adapter-emission/v1": "sha256:" + "4" * 64,
        "bicameral.external-ingest-envelope/v2": "sha256:" + "5" * 64,
        "bicameral.gateway-delivery-receipt/v1": "sha256:" + "6" * 64,
    }
    return TransformationTraceContext(
        journey_id="journey_github_issue_comment_9",
        trace_id="trace_github_delivery_9_attempt_1",
        component_revision="a" * 40,
        occurred_at="2026-07-17T18:00:00Z",
        contract_fingerprints=fingerprints,
        correlation_ids={
            "provider_event_id": "delivery-9",
            "evidence_id": "github:comment:9:v1",
        },
    )


def test_projects_complete_d1_trace_with_adjacent_digest_chain() -> None:
    projected = project_ingest_transformation_trace(_legacy_trace(), context=_context())

    assert projected["schema"] == "bicameral.transformation-trace-set/v1"
    assert [record["phase_id"] for record in projected["records"]] == [
        "PHASE-01-PROVIDER-ACQUISITION",
        "PHASE-04-OBSERVATION",
        "PHASE-05-PROVIDER-ADVISORIES",
        "PHASE-06-UNIVERSAL-NORMALIZATION",
        "PHASE-07-UNIVERSAL-ADVISORIES",
        "PHASE-08-GATEWAY-MAPPING",
        "PHASE-08-GATEWAY-DELIVERY",
    ]

    for previous, current in zip(projected["records"], projected["records"][1:]):
        assert previous["output"]["digest"] == current["input"]["digest"]
    assert all(record["authority"]["canonical"] is False for record in projected["records"])
    assert projected["records"][-1]["persistence"]["plane"] == "local_work"
    assert projected["records"][-1]["receipt"]["status"] == "completed"


def test_provider_and_universal_advisories_remain_fail_open_and_distinct() -> None:
    projected = project_ingest_transformation_trace(_legacy_trace(), context=_context())
    by_phase = {record["phase_id"]: record for record in projected["records"]}

    provider = by_phase["PHASE-05-PROVIDER-ADVISORIES"]["evaluation"]["advisories"]
    universal = by_phase["PHASE-07-UNIVERSAL-ADVISORIES"]["evaluation"]["advisories"]

    assert [item["advisory_id"] for item in provider] == ["bot_authored"]
    assert any(item["advisory_id"] == "stale_source" for item in universal)
    assert all(item["failure_mode"] == "fail_open" for item in [*provider, *universal])
    assert all(item["authority"] == "none" for item in [*provider, *universal])


def test_output_digests_are_recomputed_from_sanitized_data() -> None:
    projected = project_ingest_transformation_trace(_legacy_trace(), context=_context())

    for record in projected["records"]:
        assert record["input"]["digest"] == canonical_digest(record["input"]["data"])
        assert record["output"]["digest"] == canonical_digest(record["output"]["data"])


def test_invalid_component_revision_fails_closed() -> None:
    context = _context()
    invalid = TransformationTraceContext(
        journey_id=context.journey_id,
        trace_id=context.trace_id,
        component_revision="short",
        occurred_at=context.occurred_at,
        contract_fingerprints=context.contract_fingerprints,
    )

    with pytest.raises(
        TransformationTraceContractError,
        match="component_revision_must_be_full_sha",
    ):
        project_ingest_transformation_trace(_legacy_trace(), context=invalid)


def test_missing_contract_fingerprint_fails_closed() -> None:
    context = _context()
    fingerprints = dict(context.contract_fingerprints)
    fingerprints.pop("bicameral.external-ingest-envelope/v2")
    invalid = TransformationTraceContext(
        journey_id=context.journey_id,
        trace_id=context.trace_id,
        component_revision=context.component_revision,
        occurred_at=context.occurred_at,
        contract_fingerprints=fingerprints,
    )

    with pytest.raises(
        TransformationTraceContractError,
        match="contract_fingerprint_required:bicameral.external-ingest-envelope/v2",
    ):
        project_ingest_transformation_trace(_legacy_trace(), context=invalid)


def test_digest_chain_tampering_fails_closed() -> None:
    projected = project_ingest_transformation_trace(_legacy_trace(), context=_context())
    tampered = deepcopy(projected)
    tampered["records"][2]["input"]["data"]["title"] = "tampered"

    with pytest.raises(
        TransformationTraceContractError,
        match="record_2_input_digest_invalid",
    ):
        validate_transformation_trace_set(tampered)


def test_integrations_cannot_claim_canonical_authority() -> None:
    projected = project_ingest_transformation_trace(_legacy_trace(), context=_context())
    tampered = deepcopy(projected)
    tampered["records"][5]["authority"]["canonical"] = True

    with pytest.raises(
        TransformationTraceContractError,
        match="integrations_cannot_create_canonical_authority",
    ):
        validate_transformation_trace_set(tampered)
