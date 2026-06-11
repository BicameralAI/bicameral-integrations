# SPDX-License-Identifier: MIT
"""Behavior tests for the connector_freshness mod."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.connector_freshness import ConnectorFreshnessMod
from mods.contract import run_mod, validate_manifest

_MOD_DIR = Path(__file__).resolve().parents[1]


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def _emission(body: str) -> AdapterEmission:
    ev = SourceEvidence(
        source_ref=SourceRef(source_id="notion", ref="r1", url="https://x/1", kind="page"),
        excerpt=body, author="dev")
    return AdapterEmission(source_id="notion", title="note", body=body, evidence=(ev,))


def test_manifest_acceptance():
    validate_manifest(_manifest(), ConnectorFreshnessMod())


def test_no_freshness_term_no_output():
    assert ConnectorFreshnessMod().evaluate([_emission("Discuss the launch plan")]) == []


def test_deprecation_routes_connectors():
    out = run_mod(ConnectorFreshnessMod(),
                  [_emission("The provider deprecated the old endpoint; migrate to v3")], _manifest())
    route = [e for e in out if e.output_type == "routing_hint"]
    assert route and route[0].routing_hint is not None
    assert route[0].routing_hint.role == "connectors"


def test_soft_version_annotates_only():
    out = ConnectorFreshnessMod().evaluate([_emission("Calls the /v2/ servers endpoint")])
    kinds = [e.output_type for e in out]
    assert kinds == ["source_evidence_annotation"]  # soft mention, no route
