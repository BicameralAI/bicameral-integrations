# SPDX-License-Identifier: MIT
"""Behavior tests for the ownership_routing mod."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.contract import run_mod, validate_manifest
from mods.ownership_routing import OwnershipRoutingMod

_MOD_DIR = Path(__file__).resolve().parents[1]


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def _pr(body: str, kind: str = "pull_request") -> AdapterEmission:
    ev = SourceEvidence(
        source_ref=SourceRef(source_id="github", ref="o/r#1", url="https://x/1", kind=kind),
        excerpt=body, author="dev")
    return AdapterEmission(source_id="github", title="change", body=body, evidence=(ev,))


def test_manifest_acceptance():
    validate_manifest(_manifest(), OwnershipRoutingMod())


def test_non_change_evidence_silent():
    assert OwnershipRoutingMod().evaluate([_pr("update the connector", kind="page")]) == []


def test_no_domain_silent():
    assert OwnershipRoutingMod().evaluate([_pr("Tidy a variable name")]) == []


def test_security_change_routes_security_lens():
    out = run_mod(OwnershipRoutingMod(), [_pr("Harden the auth signature redaction")], _manifest())
    lenses = [e for e in out if e.output_type == "owner_lens_hint"]
    routes = [e for e in out if e.output_type == "routing_hint"]
    assert lenses and lenses[0].advisory is not None
    assert any(r.routing_hint and r.routing_hint.role == "security" for r in routes)


def test_multi_domain_emits_multiple_lenses():
    out = OwnershipRoutingMod().evaluate([_pr("Update the connector adapter and its docs/ readme")])
    roles = {e.routing_hint.role for e in out if e.output_type == "routing_hint" and e.routing_hint}
    assert {"connectors", "docs"} <= roles


def test_substring_false_positives_do_not_fire():
    # SG-2026-06-12-E: bare-substring superstrings must NOT route.
    assert OwnershipRoutingMod().evaluate([_pr("Rename the author field on profiles")]) == []  # not 'auth'
    assert OwnershipRoutingMod().evaluate([_pr("Rename policyholder model to member")]) == []   # not 'policy'
    assert OwnershipRoutingMod().evaluate([_pr("Add a cryptocurrency price widget")]) == []      # not 'crypto'
    assert OwnershipRoutingMod().evaluate([_pr("Optimize the quadratic sort")]) == []            # not 'adr'
