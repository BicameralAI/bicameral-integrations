# SPDX-License-Identifier: MIT
"""Behavior tests for the notification_scope_risk mod."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.contract import run_mod, validate_manifest
from mods.notification_scope_risk import NotificationScopeRiskMod

_MOD_DIR = Path(__file__).resolve().parents[1]


def _emission(title: str = "t", body: str = "b", excerpt: str = "clean text") -> AdapterEmission:
    ref = SourceRef(source_id="github", ref="o/r#1", url="https://e/1", kind="pull_request")
    ev = SourceEvidence(source_ref=ref, excerpt=excerpt, author="u")
    return AdapterEmission(source_id="github", title=title, body=body, evidence=(ev,))


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def test_surfaces_broadcast_scope_through_run_mod():
    # Keystone: the mod NAMES the over-broad scope ("@channel"/"notify all") and routes to security.
    em = _emission(body="let's just @channel everyone and notify all teams")
    out = run_mod(NotificationScopeRiskMod(), [em], _manifest())
    kinds = [e.output_type for e in out]
    assert kinds.count("advisory_governance_result") == 1
    assert "routing_hint" in kinds and "suggested_review_question" in kinds
    route = next(e for e in out if e.output_type == "routing_hint")
    assert route.routing_hint is not None and route.routing_hint.role == "security"
    adv = next(e for e in out if e.output_type == "advisory_governance_result")
    assert adv.advisory is not None
    assert "@channel" in adv.advisory.message and "notify all" in adv.advisory.message


def test_clean_body_no_op():
    assert NotificationScopeRiskMod().evaluate([_emission(body="scoped DM to the on-call engineer")]) == []


def test_word_boundary_safety_negative():
    # "broadcast" alone is intentionally NOT a term, so "broadcaster" / a lone "broadcast" never fire.
    assert NotificationScopeRiskMod().evaluate([_emission(body="the broadcaster scheduled a stream")]) == []


def test_manifest_accept():
    validate_manifest(_manifest(), NotificationScopeRiskMod())
