# SPDX-License-Identifier: MIT
"""Behavior tests for the code_review_risk mod."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.code_review_risk import CodeReviewRiskMod
from mods.contract import run_mod, validate_manifest

_MOD_DIR = Path(__file__).resolve().parents[1]


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def _pr(body: str, kind: str = "pull_request") -> AdapterEmission:
    ev = SourceEvidence(
        source_ref=SourceRef(source_id="github", ref="o/r#1", url="https://x/1", kind=kind),
        excerpt=body, author="dev")
    return AdapterEmission(source_id="github", title="change", body=body, evidence=(ev,))


def test_manifest_acceptance():
    validate_manifest(_manifest(), CodeReviewRiskMod())


def test_non_change_evidence_silent():
    # only fires on change evidence (PR/issue/MR); a page mention is ignored.
    assert CodeReviewRiskMod().evaluate([_pr("auth migration", kind="page")]) == []


def test_low_risk_change_silent():
    assert CodeReviewRiskMod().evaluate([_pr("Tweak a log message")]) == []


def test_risky_area_routes_and_asks():
    out = run_mod(CodeReviewRiskMod(), [_pr("Add a DB migration and an auth token change")], _manifest())
    kinds = [e.output_type for e in out]
    assert "routing_hint" in kinds and "suggested_review_question" in kinds
    route = next(e for e in out if e.output_type == "routing_hint")
    assert route.routing_hint is not None and route.routing_hint.priority == "high"
