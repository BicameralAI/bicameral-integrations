# SPDX-License-Identifier: MIT
"""Behavior tests for the noisy_source_gate mod (FX-MOD-003)."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.contract import run_mod, validate_manifest
from mods.noisy_source_gate import NoisySourceGateMod

_MOD_DIR = Path(__file__).resolve().parents[1]


def _emission(source_id: str) -> AdapterEmission:
    ref = SourceRef(source_id=source_id, ref="x/1", url="https://e/1", kind="message")
    ev = SourceEvidence(source_ref=ref, excerpt="some chatter", author="u")  # valid non-blank evidence
    return AdapterEmission(source_id=source_id, title="t", body="b", evidence=(ev,))


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def test_gates_noisy_source():
    out = run_mod(NoisySourceGateMod(), [_emission("slack")], _manifest())
    kinds = [e.output_type for e in out]
    assert "routing_hint" in kinds and "advisory_governance_result" in kinds
    route = next(e for e in out if e.output_type == "routing_hint")
    assert route.routing_hint is not None and route.routing_hint.role == "reviewer"


def test_no_gate_for_clean_source():
    assert NoisySourceGateMod().evaluate([_emission("linear")]) == []


def test_manifest_accept():
    validate_manifest(_manifest(), NoisySourceGateMod())  # outputs set-equality
