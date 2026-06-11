"""Behavior tests for the data_classification mod + EM-safe contract compliance."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods.contract import load_manifest, run_mod, validate_manifest
from mods.data_classification import DataClassificationMod

_MANIFEST = Path(__file__).resolve().parents[1] / "manifest.yaml"


def _em(text: str, *, title: str = "t") -> AdapterEmission:
    ev = SourceEvidence(source_ref=SourceRef(source_id="x", ref="r1"), excerpt=text)
    return AdapterEmission(
        source_id="x", title=title, body=text, evidence=(ev,),
        emission_type="candidate", adapter_version="dc-test/1", metadata={},
    )


def test_flags_confidentiality_marker():
    out = DataClassificationMod().evaluate([_em("This design is CONFIDENTIAL, do not share.")])
    assert {e.output_type for e in out} == {
        "source_evidence_annotation", "routing_hint", "advisory_governance_result"}
    ann = next(e for e in out if e.output_type == "source_evidence_annotation")
    assert ann.advisory.metadata["classification"] == "restricted"
    assert "confidential" in ann.advisory.metadata["signals"]


def test_flags_redaction_placeholder():
    out = DataClassificationMod().evaluate([_em("ping [redacted:email] before merge")])
    rh = [e for e in out if e.output_type == "routing_hint"]
    assert rh and rh[0].routing_hint.role == "restricted-review"
    ann = next(e for e in out if e.output_type == "source_evidence_annotation")
    assert "redacted-pii" in ann.advisory.metadata["signals"]


def test_general_evidence_yields_no_annotation():
    assert DataClassificationMod().evaluate([_em("We adopted Postgres for the event store.")]) == []


def test_run_mod_contract_compliant():
    mod = DataClassificationMod()
    manifest = load_manifest(_MANIFEST)
    validate_manifest(manifest, mod)  # id/version/outputs mirror manifest + EM-safe baseline
    results = run_mod(mod, [_em("internal-only proprietary roadmap")], manifest)
    assert results  # emits + passes outputs-allowlist, no-opaque-score, and FX-SEC-001 screen
    assert all(e.output_type in mod.outputs for e in results)
