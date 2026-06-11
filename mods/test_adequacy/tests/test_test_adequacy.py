# SPDX-License-Identifier: MIT
"""Behavior tests for the test_adequacy mod."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.contract import run_mod, validate_manifest
from mods.test_adequacy import TestAdequacyMod

_MOD_DIR = Path(__file__).resolve().parents[1]


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def _pr(body: str, kind: str = "pull_request") -> AdapterEmission:
    ev = SourceEvidence(
        source_ref=SourceRef(source_id="github", ref="o/r#1", url="https://x/1", kind=kind),
        excerpt=body, author="dev")
    return AdapterEmission(source_id="github", title="change", body=body, evidence=(ev,))


def test_manifest_acceptance():
    validate_manifest(_manifest(), TestAdequacyMod())


def test_behavior_change_with_tests_silent():
    assert TestAdequacyMod().evaluate([_pr("Fix the parser bug and add a unit test")]) == []


def test_non_behavior_change_silent():
    assert TestAdequacyMod().evaluate([_pr("Update the README wording")]) == []


def test_behavior_change_without_tests_routes_and_asks():
    out = run_mod(TestAdequacyMod(), [_pr("Fix a regression in the validation handler")], _manifest())
    kinds = [e.output_type for e in out]
    assert "routing_hint" in kinds and "suggested_review_question" in kinds
    assert any("test gap" in e.advisory.message for e in out if e.advisory)


def test_latest_does_not_suppress_test_gap():
    # the medium: 'test' must NOT match inside 'latest', which used to suppress the real gap.
    out = run_mod(TestAdequacyMod(), [_pr("Fix a regression in the latest validation logic")], _manifest())
    assert any("test gap" in e.advisory.message for e in out if e.advisory)


def test_prefix_does_not_fire_behavior():
    # 'fix' must NOT match inside 'prefix' (SG-2026-06-12-E).
    assert TestAdequacyMod().evaluate([_pr("Document the prefix naming convention")]) == []
