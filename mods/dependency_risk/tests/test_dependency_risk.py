# SPDX-License-Identifier: MIT
"""Behavior tests for the dependency_risk reference mod (FX-MOD-002)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from adapter.core.pipeline import EmissionContractError, normalize
from connectors.osv.connector import parse_vuln
from mods._manifest import load_manifest
from mods.contract import run_mod, validate_manifest
from mods.dependency_risk import DependencyRiskMod

_MOD_DIR = Path(__file__).resolve().parents[1]
_REPO = Path(__file__).resolve().parents[3]
_OSV_FIXTURE = _REPO / "connectors" / "osv" / "fixtures" / "vulnerability.json"


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def _osv_emissions() -> list[AdapterEmission]:
    record = json.loads(_OSV_FIXTURE.read_text(encoding="utf-8"))
    return normalize([parse_vuln(record)], adapter_version="osv/0.1.0")


def _pr_emission(body: str, ref: str = "o/r#1") -> AdapterEmission:
    ev = SourceEvidence(
        source_ref=SourceRef(source_id="github", ref=ref,
                             url="https://github.com/o/r/pull/1", kind="pull_request"),
        excerpt=body, author="dev",
    )
    return AdapterEmission(source_id="github", title="Update deps", body=body, evidence=(ev,))


def test_osv_vulnerability_end_to_end():
    # OSV fixture → parse → normalize (metadata preserved, ADR-0014) → mod. Proves the chain.
    out = run_mod(DependencyRiskMod(), _osv_emissions(), _manifest())
    sig = [e for e in out if e.output_type == "dependency_signal"]
    route = [e for e in out if e.output_type == "routing_hint"]
    assert sig and sig[0].advisory is not None
    assert sig[0].advisory.metadata["packages"] == "example-pkg"
    assert route and route[0].routing_hint is not None
    assert route[0].routing_hint.role == "security"
    assert route[0].routing_hint.priority == "high"  # CVE-2026-0001 alias present


def test_manifest_acceptance():
    # outputs must EXACTLY mirror manifest.yaml (run_mod's validate_manifest set-equality).
    validate_manifest(_manifest(), DependencyRiskMod())  # must not raise


def test_manifest_mention_path():
    em = _pr_emission("bump deps declared in requirements.txt")
    out = DependencyRiskMod().evaluate([em])
    kinds = [e.output_type for e in out]
    assert kinds.count("dependency_signal") == 1
    assert kinds.count("source_evidence_annotation") == 1
    assert "routing_hint" not in kinds  # text path is too low-confidence to route


def test_no_false_positive():
    # an ordinary emission (no vuln evidence, no manifest token) yields NOTHING.
    em = _pr_emission("Refactor the auth handler; no build changes here")
    assert DependencyRiskMod().evaluate([em]) == []


def test_secret_in_input_ref_rejected():
    # the mod must not smuggle: a planted secret in source_ref.ref is HARD-rejected by run_mod.
    poisoned = _pr_emission("update package.json", ref="token-AKIAIOSFODNN7EXAMPLE")
    with pytest.raises(EmissionContractError):
        run_mod(DependencyRiskMod(), [poisoned], _manifest())
