# SPDX-License-Identifier: MIT
"""Behavior tests for the ai_authorship_review mod."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.ai_authorship_review import AiAuthorshipReviewMod
from mods.contract import run_mod, validate_manifest

_MOD_DIR = Path(__file__).resolve().parents[1]


def _emission(
    source_id: str = "cursor",
    title: str = "t",
    body: str = "b",
    excerpt: str = "clean text",
) -> AdapterEmission:
    ref = SourceRef(source_id=source_id, ref="o/r#1", url="https://e/1", kind="pull_request")
    ev = SourceEvidence(source_ref=ref, excerpt=excerpt, author="u")
    return AdapterEmission(source_id=source_id, title=title, body=body, evidence=(ev,))


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def test_ai_source_with_markers_routes_to_qa_through_run_mod():
    # AI source (cursor) + uncertainty markers -> 3 advisory outputs, QA route, markers named.
    em = _emission(
        source_id="cursor",
        body="TODO: finish this; I'm not sure the edge case is handled",
    )
    out = run_mod(AiAuthorshipReviewMod(), [em], _manifest())
    kinds = [e.output_type for e in out]
    assert kinds.count("advisory_governance_result") == 1
    assert "routing_hint" in kinds and "suggested_review_question" in kinds
    assert len(out) == 3
    route = next(e for e in out if e.output_type == "routing_hint")
    assert route.routing_hint is not None and route.routing_hint.role == "qa"
    adv = next(e for e in out if e.output_type == "advisory_governance_result")
    assert adv.advisory is not None
    assert "todo" in adv.advisory.message and "not sure" in adv.advisory.message


def test_non_ai_source_is_skipped_even_with_markers():
    # Same markers, but a non-AI source (github) -> nothing fires (the source gate).
    em = _emission(
        source_id="github",
        body="TODO: finish this; I'm not sure the edge case is handled",
    )
    assert AiAuthorshipReviewMod().evaluate([em]) == []


def test_ai_source_clean_no_op():
    # AI source but no uncertainty markers -> nothing fires.
    em = _emission(source_id="cursor", body="just a routine refactor of the parser")
    assert AiAuthorshipReviewMod().evaluate([em]) == []


def test_manifest_accept():
    validate_manifest(_manifest(), AiAuthorshipReviewMod())
