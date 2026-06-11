# SPDX-License-Identifier: MIT
"""Behavior tests for the authority_boundary mod."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.authority_boundary import AuthorityBoundaryMod
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
    validate_manifest(_manifest(), AuthorityBoundaryMod())


def test_ordinary_change_silent():
    assert AuthorityBoundaryMod().evaluate([_pr("Rename a helper function")]) == []


def test_non_change_evidence_silent():
    assert AuthorityBoundaryMod().evaluate([_pr("auto-merge enabled", kind="message")]) == []


def test_authority_crossing_routes_governance():
    out = run_mod(AuthorityBoundaryMod(),
                  [_pr("Enable auto-merge and skip review for deploy to production")], _manifest())
    kinds = [e.output_type for e in out]
    assert "routing_hint" in kinds and "suggested_review_question" in kinds
    route = next(e for e in out if e.output_type == "routing_hint")
    assert route.routing_hint is not None and route.routing_hint.role == "governance"
