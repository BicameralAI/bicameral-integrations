# SPDX-License-Identifier: MIT
"""Behavior tests for the decision_drift mod."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.contract import run_mod, validate_manifest
from mods.decision_drift import DecisionDriftMod

_MOD_DIR = Path(__file__).resolve().parents[1]


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def _emission(body: str, kind: str = "issue") -> AdapterEmission:
    ev = SourceEvidence(
        source_ref=SourceRef(source_id="jira", ref="PROJ-1", url="https://x/1", kind=kind),
        excerpt=body, author="dev")
    return AdapterEmission(source_id="jira", title="note", body=body, evidence=(ev,))


def test_manifest_acceptance():
    validate_manifest(_manifest(), DecisionDriftMod())


def test_anchor_without_cue_silent():
    # an ADR mention with no conflict verb is not drift.
    assert DecisionDriftMod().evaluate([_emission("Implements ADR-0013 as specified")]) == []


def test_cue_without_anchor_silent():
    assert DecisionDriftMod().evaluate([_emission("This supersedes the old caching helper")]) == []


def test_anchor_and_cue_routes_governance_and_asks():
    out = run_mod(DecisionDriftMod(),
                  [_emission("This supersedes ADR-0008 and the recorded trust tier")], _manifest())
    kinds = [e.output_type for e in out]
    assert "routing_hint" in kinds and "suggested_review_question" in kinds
    route = next(e for e in out if e.output_type == "routing_hint")
    assert route.routing_hint is not None and route.routing_hint.role == "governance"


def test_not_gated_to_change_evidence():
    # decision drift can come from a meeting note (kind=meeting), unlike the PR-review family.
    out = DecisionDriftMod().evaluate(
        [_emission("The recorded decision is now obsolete", kind="meeting")])
    assert any(e.output_type == "advisory_governance_result" for e in out)


def test_adr_substring_does_not_fire():
    # SG-2026-06-12-E: 'adr' must NOT match inside 'quadratic' (even with a real conflict cue).
    assert DecisionDriftMod().evaluate(
        [_emission("The quadratic model supersedes the prior estimate")]) == []
