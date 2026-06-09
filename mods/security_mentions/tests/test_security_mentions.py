# SPDX-License-Identifier: MIT
"""Behavior tests for the security_mentions mod (FX-MOD-004)."""

from __future__ import annotations

from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from mods._manifest import load_manifest
from mods.contract import run_mod, validate_manifest
from mods.security_mentions import SecurityMentionsMod

_MOD_DIR = Path(__file__).resolve().parents[1]


def _emission(title: str = "t", body: str = "b", excerpt: str = "clean text") -> AdapterEmission:
    ref = SourceRef(source_id="github", ref="o/r#1", url="https://e/1", kind="pull_request")
    ev = SourceEvidence(source_ref=ref, excerpt=excerpt, author="u")
    return AdapterEmission(source_id="github", title=title, body=body, evidence=(ev,))


def _manifest():
    return load_manifest(_MOD_DIR / "manifest.yaml")


def test_surfaces_security_mentions_through_run_mod():
    # Keystone (advisory #2): the mod NAMES what it found ("oauth"/"secret"/"token") and still passes
    # run_mod's FX-SEC-001 input+output screen — a mention is not a secret shape.
    em = _emission(body="rotate the oauth token; the old secret is rotated")
    out = run_mod(SecurityMentionsMod(), [em], _manifest())
    kinds = [e.output_type for e in out]
    assert kinds.count("advisory_governance_result") == 1
    assert "routing_hint" in kinds and "source_evidence_annotation" in kinds
    route = next(e for e in out if e.output_type == "routing_hint")
    assert route.routing_hint is not None and route.routing_hint.role == "security"
    adv = next(e for e in out if e.output_type == "advisory_governance_result")
    assert adv.advisory is not None and "oauth" in adv.advisory.message and "token" in adv.advisory.message


def test_clean_body_no_op():
    assert SecurityMentionsMod().evaluate([_emission(body="just a normal refactor of the parser")]) == []


def test_whole_word_boundaries():
    # advisory #1: \btoken\b does NOT fire on "tokenize"; "cve" DOES fire on a catalogued id.
    assert SecurityMentionsMod().evaluate([_emission(body="tokenize the input stream")]) == []
    assert SecurityMentionsMod().evaluate([_emission(body="see CVE-2026-0001 for details")])


def test_keyword_in_excerpt_only():
    # advisory #3: a keyword present ONLY in the evidence excerpt is surfaced (excerpt is scanned).
    em = _emission(title="x", body="y", excerpt="please rotate the api credential next sprint")
    assert SecurityMentionsMod().evaluate([em])


def test_manifest_accept():
    validate_manifest(_manifest(), SecurityMentionsMod())
