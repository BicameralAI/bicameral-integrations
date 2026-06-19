# SPDX-License-Identifier: MIT
"""Behavior tests for the compliance_routing mod (FX-MOD)."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.compliance_routing import ComplianceRoutingMod
from mods.contract import run_mod, validate_manifest

_MOD_DIR = Path(__file__).resolve().parents[1]


def _emission(title: str = "t", body: str = "b", excerpt: str = "clean text") -> AdapterEmission:
    ref = SourceRef(source_id="github", ref="o/r#1", url="https://e/1", kind="pull_request")
    ev = SourceEvidence(source_ref=ref, excerpt=excerpt, author="u")
    return AdapterEmission(source_id="github", title=title, body=body, evidence=(ev,))


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def test_surfaces_named_framework_through_run_mod():
    # Keystone: evidence naming a regulatory framework yields all 3 advisory outputs, a
    # high-priority COMPLIANCE route, and the framework in the governance message — and passes
    # run_mod's FX-SEC-001 input+output screen (a framework name is not a secret shape).
    em = _emission(body="this endpoint handles PHI and must meet HIPAA controls")
    out = run_mod(ComplianceRoutingMod(), [em], _manifest())
    kinds = [e.output_type for e in out]
    assert kinds.count("advisory_governance_result") == 1
    assert kinds.count("routing_hint") == 1
    assert kinds.count("suggested_review_question") == 1
    route = next(e for e in out if e.output_type == "routing_hint")
    assert route.routing_hint is not None
    assert route.routing_hint.role == "compliance"
    assert route.routing_hint.priority == "high"
    adv = next(e for e in out if e.output_type == "advisory_governance_result")
    assert adv.advisory is not None and "hipaa" in adv.advisory.message


def test_clean_body_no_op():
    assert ComplianceRoutingMod().evaluate([_emission(body="just a normal refactor of the parser")]) == []


def test_whole_word_boundary_no_false_fire():
    # "sox" is a pure-alnum term, so matched_terms word-boundary-matches it as a whole token.
    # "soxhlet" is a single token != "sox", so it correctly does NOT fire (no substring leak).
    assert ComplianceRoutingMod().evaluate([_emission(body="cleaned with the soxhlet extractor")]) == []
    # Sanity: the bare token DOES fire.
    assert ComplianceRoutingMod().evaluate([_emission(body="this change affects SOX controls")])


def test_manifest_accept():
    validate_manifest(_manifest(), ComplianceRoutingMod())
