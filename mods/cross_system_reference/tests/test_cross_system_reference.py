# SPDX-License-Identifier: MIT
"""Behavior tests for the cross_system_reference mod (FX-MOD)."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.contract import run_mod, validate_manifest
from mods.cross_system_reference import CrossSystemReferenceMod

_MOD_DIR = Path(__file__).resolve().parents[1]


def _emission(
    source_id: str = "linear",
    title: str = "t",
    body: str = "b",
    excerpt: str = "clean text",
) -> AdapterEmission:
    ref = SourceRef(source_id=source_id, ref="o/r#1", url="https://e/1", kind="issue")
    ev = SourceEvidence(source_ref=ref, excerpt=excerpt, author="u")
    return AdapterEmission(source_id=source_id, title=title, body=body, evidence=(ev,))


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def test_surfaces_cross_system_reference_through_run_mod():
    # Keystone: a Linear emission whose body links a github.com PR -> all 3 outputs, integrations
    # route, and the foreign system named in the annotation. Passes run_mod's FX-SEC-001 screen.
    em = _emission(source_id="linear", body="tracks the fix in https://github.com/o/r/pull/42")
    out = run_mod(CrossSystemReferenceMod(), [em], _manifest())
    kinds = [e.output_type for e in out]
    assert kinds.count("source_evidence_annotation") == 1
    assert kinds.count("suggested_review_question") == 1
    assert kinds.count("routing_hint") == 1
    route = next(e for e in out if e.output_type == "routing_hint")
    assert route.routing_hint is not None and route.routing_hint.role == "integrations"
    ann = next(e for e in out if e.output_type == "source_evidence_annotation")
    assert ann.advisory is not None and "github" in ann.advisory.message


def test_self_reference_no_op():
    # A github emission mentioning ONLY github.com is not cross-system -> [].
    em = _emission(source_id="github", body="see https://github.com/o/r/pull/42")
    assert CrossSystemReferenceMod().evaluate([em]) == []


def test_clean_body_no_op():
    em = _emission(source_id="linear", body="just a normal refactor of the parser")
    assert CrossSystemReferenceMod().evaluate([em]) == []


def test_manifest_accept():
    validate_manifest(_manifest(), CrossSystemReferenceMod())
