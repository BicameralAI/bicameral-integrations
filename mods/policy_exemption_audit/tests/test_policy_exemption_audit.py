# SPDX-License-Identifier: MIT
"""Behavior tests for the policy_exemption_audit mod (FX-MOD)."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.contract import run_mod, validate_manifest
from mods.policy_exemption_audit import PolicyExemptionAuditMod

_MOD_DIR = Path(__file__).resolve().parents[1]


def _emission(title: str = "t", body: str = "b", excerpt: str = "clean text") -> AdapterEmission:
    ref = SourceRef(source_id="github", ref="o/r#1", url="https://e/1", kind="pull_request")
    ev = SourceEvidence(source_ref=ref, excerpt=excerpt, author="u")
    return AdapterEmission(source_id="github", title=title, body=body, evidence=(ev,))


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def test_surfaces_exemption_claim_through_run_mod():
    # Keystone: an exemption claim yields all 3 advisory outputs, a high-priority POLICY route,
    # and the matched term in the governance message — and passes run_mod's FX-SEC-001 screen.
    em = _emission(body="this finding is wontfix; risk accepted for now")
    out = run_mod(PolicyExemptionAuditMod(), [em], _manifest())
    kinds = [e.output_type for e in out]
    assert kinds.count("advisory_governance_result") == 1
    assert kinds.count("routing_hint") == 1
    assert kinds.count("suggested_review_question") == 1
    route = next(e for e in out if e.output_type == "routing_hint")
    assert route.routing_hint is not None
    assert route.routing_hint.role == "policy"
    assert route.routing_hint.priority == "high"
    adv = next(e for e in out if e.output_type == "advisory_governance_result")
    assert adv.advisory is not None and "wontfix" in adv.advisory.message


def test_clean_body_no_op():
    assert PolicyExemptionAuditMod().evaluate([_emission(body="just a normal refactor of the parser")]) == []


def test_authority_phrase_without_exemption_does_not_fire():
    # No overlap with authority_boundary: an authority-ACTION phrase with NO exemption term
    # must not fire here (authority_boundary owns "auto-merge"/"bypass governance").
    assert PolicyExemptionAuditMod().evaluate([_emission(body="auto-merge enabled")]) == []
    assert PolicyExemptionAuditMod().evaluate([_emission(body="bypass governance to land this")]) == []


def test_manifest_accept():
    validate_manifest(_manifest(), PolicyExemptionAuditMod())
