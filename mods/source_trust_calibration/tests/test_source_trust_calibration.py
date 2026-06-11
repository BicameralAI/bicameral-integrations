# SPDX-License-Identifier: MIT
"""Behavior tests for the source_trust_calibration mod."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.contract import run_mod, validate_manifest
from mods.source_trust_calibration import SourceTrustCalibrationMod

_MOD_DIR = Path(__file__).resolve().parents[1]


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def _emission(*, source_id="github", kind="pull_request", author="dev",
              emission_type="candidate") -> AdapterEmission:
    ev = SourceEvidence(
        source_ref=SourceRef(source_id=source_id, ref="r1", url="https://x/1", kind=kind),
        excerpt="content", author=author)
    return AdapterEmission(source_id=source_id, title="t", body="b", evidence=(ev,),
                           emission_type=emission_type)


def test_manifest_acceptance():
    validate_manifest(_manifest(), SourceTrustCalibrationMod())


def test_well_provenanced_emission_no_output():
    assert SourceTrustCalibrationMod().evaluate([_emission()]) == []


def test_missing_actor_identity_routes():
    out = run_mod(SourceTrustCalibrationMod(), [_emission(author="")], _manifest())
    kinds = [e.output_type for e in out]
    assert "routing_hint" in kinds
    route = next(e for e in out if e.output_type == "routing_hint")
    assert route.routing_hint is not None and route.routing_hint.role == "review"
    assert any("no actor identity" in e.advisory.message for e in out if e.advisory)


def test_public_source_flagged():
    out = SourceTrustCalibrationMod().evaluate([_emission(source_id="mcp_registry", kind="mcp_server")])
    assert any("public/no-auth" in e.advisory.message for e in out if e.advisory)


def test_unknown_kind_flagged():
    out = SourceTrustCalibrationMod().evaluate([_emission(kind="")])
    assert any("unknown schema" in e.advisory.message for e in out if e.advisory)
