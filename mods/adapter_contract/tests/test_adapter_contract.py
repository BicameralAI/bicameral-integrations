# SPDX-License-Identifier: MIT
"""Behavior tests for the adapter_contract mod."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.adapter_contract import AdapterContractMod
from mods.contract import run_mod, validate_manifest

_MOD_DIR = Path(__file__).resolve().parents[1]


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def _emission(*, ref="o/r#1", url="https://x/1", excerpt="changed something",
              kind="pull_request", evidence=True) -> AdapterEmission:
    evs = ()
    if evidence:
        evs = (SourceEvidence(
            source_ref=SourceRef(source_id="github", ref=ref, url=url, kind=kind),
            excerpt=excerpt, author="dev"),)
    return AdapterEmission(source_id="github", title="t", body="b", evidence=evs)


def test_manifest_acceptance():
    validate_manifest(_manifest(), AdapterContractMod())  # outputs mirror manifest.yaml


def test_well_formed_emission_no_output():
    assert AdapterContractMod().evaluate([_emission()]) == []


def test_lost_pointer_routes():
    # evidence with neither ref nor url cannot be tied to its source -> annotate + advise + route.
    out = run_mod(AdapterContractMod(), [_emission(ref="", url="")], _manifest())
    kinds = [e.output_type for e in out]
    assert "routing_hint" in kinds
    route = next(e for e in out if e.output_type == "routing_hint")
    assert route.routing_hint is not None and route.routing_hint.role == "connectors"


def test_zero_evidence_routes():
    out = AdapterContractMod().evaluate([_emission(evidence=False)])
    kinds = [e.output_type for e in out]
    assert "routing_hint" in kinds  # no reviewable pointer at all
    assert any("zero SourceEvidence" in e.advisory.message for e in out if e.advisory)


def test_blank_excerpt_annotates_without_routing():
    # a blank excerpt is a nit (ref/url still locate it) -> annotate, do NOT route.
    out = AdapterContractMod().evaluate([_emission(excerpt="   ")])
    kinds = [e.output_type for e in out]
    assert "source_evidence_annotation" in kinds
    assert "routing_hint" not in kinds
