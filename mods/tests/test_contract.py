# SPDX-License-Identifier: MIT
"""Behavior tests for the mod execution contract (ADR-0013)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from adapter.core.emissions import AdapterEmission, AdvisoryResult, RoutingHint, SourceEvidence, SourceRef
from adapter.core.pipeline import EmissionContractError
from mods._manifest import ModManifestError
from mods.contract import (
    _EM_SAFE_FORBIDDEN,
    _KNOWN_OUTPUTS,
    Manifest,
    ModContractError,
    ModEmission,
    load_manifest,
    run_mod,
    validate_manifest,
)

_MODS_DIR = Path(__file__).resolve().parents[1]


def _emission(body: str = "a normal pull request body") -> AdapterEmission:
    ref = SourceRef(source_id="github", ref="pr/1", url="https://example/pr/1", kind="pull_request")
    ev = SourceEvidence(source_ref=ref, excerpt="diff excerpt", author="dev")
    return AdapterEmission(source_id="github", title="PR #1", body=body, evidence=(ev,))


class _FakeMod:
    """A minimal Mod for the runner tests (no real mod logic)."""

    def __init__(self, *, outputs, results, id="dependency-risk", version="0.1.0"):
        self.id = id
        self.version = version
        self.outputs = frozenset(outputs)
        self._results = results

    def evaluate(self, emissions):  # noqa: ARG002 — fixed results for the test
        return list(self._results)


def _manifest(outputs, *, id="dependency-risk", version="0.1.0", forbidden=None) -> Manifest:
    return Manifest(
        id=id, version=version, name="X",
        outputs=frozenset(outputs),
        forbidden_actions=frozenset(forbidden if forbidden is not None else _EM_SAFE_FORBIDDEN),
    )


def test_run_mod_emits_declared_outputs():
    results = [
        ModEmission("advisory_governance_result", advisory=AdvisoryResult(kind="advisory_governance_result", message="ok")),
        ModEmission("routing_hint", routing_hint=RoutingHint(role="security", reason="review")),
    ]
    mod = _FakeMod(outputs={"advisory_governance_result", "routing_hint"}, results=results)
    out = run_mod(mod, [_emission()], _manifest(mod.outputs))
    assert len(out) == 2


def test_owner_lens_and_review_question_outputs():
    # F1: non-routing kinds (owner_lens_hint, suggested_review_question) ride on AdvisoryResult.kind
    results = [
        ModEmission("owner_lens_hint", advisory=AdvisoryResult(kind="owner_lens_hint", message="payments owns this")),
        ModEmission("suggested_review_question", advisory=AdvisoryResult(kind="suggested_review_question", message="intended?")),
    ]
    mod = _FakeMod(outputs={"owner_lens_hint", "suggested_review_question"}, results=results)
    out = run_mod(mod, [_emission()], _manifest(mod.outputs))
    assert {e.output_type for e in out} == {"owner_lens_hint", "suggested_review_question"}


def test_output_type_must_match_artifact():
    # F2: output_type 'routing_hint' with an advisory artifact is rejected at construction
    with pytest.raises(ModContractError):
        ModEmission("routing_hint", advisory=AdvisoryResult(kind="routing_hint", message="x"))
    with pytest.raises(ModContractError):  # neither populated
        ModEmission("advisory_governance_result")
    with pytest.raises(ModContractError):  # advisory.kind != output_type
        ModEmission("dependency_signal", advisory=AdvisoryResult(kind="other", message="x"))


def test_undeclared_output_rejected():
    results = [ModEmission("routing_hint", routing_hint=RoutingHint(role="r", reason="x"))]
    mod = _FakeMod(outputs={"routing_hint"}, results=results)
    # manifest/code agree on {routing_hint} but the mod returns an output not in its set:
    rogue = _FakeMod(outputs={"routing_hint"},
                     results=[ModEmission("dependency_signal", advisory=AdvisoryResult(kind="dependency_signal", message="x"))])
    with pytest.raises(ModContractError):
        run_mod(rogue, [_emission()], _manifest({"routing_hint"}))
    assert run_mod(mod, [_emission()], _manifest({"routing_hint"}))  # the conformant one is fine


def test_manifest_forbidden_actions_enforced():
    mod = _FakeMod(outputs={"routing_hint"}, results=[])
    short = _manifest({"routing_hint"}, forbidden={"write_canonical_decision"})  # missing the rest
    with pytest.raises(ModContractError):
        validate_manifest(short, mod)


def test_manifest_id_version_outputs_must_match():
    mod = _FakeMod(outputs={"routing_hint"}, results=[], id="dependency-risk", version="0.1.0")
    with pytest.raises(ModContractError):  # id mismatch
        validate_manifest(_manifest({"routing_hint"}, id="other"), mod)
    with pytest.raises(ModContractError):  # version mismatch
        validate_manifest(_manifest({"routing_hint"}, version="9.9.9"), mod)
    with pytest.raises(ModContractError):  # outputs mismatch
        validate_manifest(_manifest({"dependency_signal"}), mod)


def test_evidence_is_immutable():
    em = _emission()
    with pytest.raises(FrozenInstanceError):
        em.title = "tampered"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        em.evidence[0].excerpt = "tampered"  # type: ignore[misc]


def test_no_opaque_score():
    results = [ModEmission("dependency_signal",
                           advisory=AdvisoryResult(kind="dependency_signal", message="risky", metadata={"score": 0.9}))]
    mod = _FakeMod(outputs={"dependency_signal"}, results=results)
    with pytest.raises(ModContractError):
        run_mod(mod, [_emission()], _manifest({"dependency_signal"}))


@pytest.mark.parametrize("metadata", [
    {"confidence_score": 0.92},          # alias key (substring match, not exact)
    {"match_probability": 0.7},          # synonym token
    {"scores": {"overall": 0.9}},        # nested under a non-literal key
    {"signals": [{"risk_score": 0.8}]},  # nested inside a list of dicts
])
def test_opaque_score_aliases_and_nesting_rejected(metadata):
    # Hardening: a numeric score smuggled under an alias or nested key is still rejected.
    results = [ModEmission("dependency_signal",
                           advisory=AdvisoryResult(kind="dependency_signal", message="risky", metadata=metadata))]
    mod = _FakeMod(outputs={"dependency_signal"}, results=results)
    with pytest.raises(ModContractError):
        run_mod(mod, [_emission()], _manifest({"dependency_signal"}))


def test_opaque_score_allows_legit_counts():
    # A plain count is not a score — `score`/`confidence`/etc. substrings absent → allowed.
    results = [ModEmission("dependency_signal",
                           advisory=AdvisoryResult(kind="dependency_signal", message="3 outdated deps",
                                                   metadata={"outdated_count": 3, "flagged": True}))]
    mod = _FakeMod(outputs={"dependency_signal"}, results=results)
    assert run_mod(mod, [_emission()], _manifest({"dependency_signal"}))


def test_mod_output_sensitive_data_rejected():
    # F6: a mod that surfaces a PAN in its advisory message is HARD-rejected by the runner.
    results = [ModEmission("advisory_governance_result",
                           advisory=AdvisoryResult(kind="advisory_governance_result",
                                                   message="leaked card 4111111111111111 in the body"))]
    mod = _FakeMod(outputs={"advisory_governance_result"}, results=results)
    with pytest.raises(ModContractError):
        run_mod(mod, [_emission()], _manifest({"advisory_governance_result"}))


def test_sensitive_data_rejected_in_output_metadata_key():
    # A mod must not exfiltrate a secret by smuggling it into an output-metadata KEY.
    results = [ModEmission("dependency_signal",
                           advisory=AdvisoryResult(kind="dependency_signal", message="ok",
                                                   metadata={"AKIAIOSFODNN7EXAMPLE": "v"}))]
    mod = _FakeMod(outputs={"dependency_signal"}, results=results)
    with pytest.raises(ModContractError):
        run_mod(mod, [_emission()], _manifest({"dependency_signal"}))


def test_sensitive_data_rejected_in_evidence_ids_and_nested_metadata():
    # Hardening: the FX-SEC-001 screen covers ALL wire-bound fields, not just `message`.
    pan = "4111111111111111"
    via_ids = ModEmission("dependency_signal",
                          advisory=AdvisoryResult(kind="dependency_signal", message="ok",
                                                  evidence_ids=(f"leaked card {pan}",)))
    via_meta = ModEmission("dependency_signal",
                           advisory=AdvisoryResult(kind="dependency_signal", message="ok",
                                                   metadata={"detail": {"raw": f"card {pan} found"}}))
    for em in (via_ids, via_meta):
        mod = _FakeMod(outputs={"dependency_signal"}, results=[em])
        with pytest.raises(ModContractError):
            run_mod(mod, [_emission()], _manifest({"dependency_signal"}))


def test_load_manifest_parses_real_dependency_risk():
    m = load_manifest(_MODS_DIR / "dependency_risk" / "manifest.yaml")
    assert m.id == "dependency-risk"
    assert m.version == "0.1.0" and isinstance(m.version, str)  # str, not float
    assert "dependency_signal" in m.outputs
    assert m.forbidden_actions >= _EM_SAFE_FORBIDDEN


def test_load_manifest_rejects_malformed(tmp_path):
    bad = [
        "id: x\nversion: 1\nname: X\noutputs:\n  nested:\n    - a\nforbidden_actions:\n  - write_canonical_decision\n",  # nested map
        "id: x\nid: y\nversion: 1\nname: X\noutputs:\n  - a\nforbidden_actions:\n  - x\n",  # duplicate key
        "id: x\nversion: 1\nname: X\nbogus: 1\noutputs:\n  - a\nforbidden_actions:\n  - x\n",  # unknown key
        "id: x\nversion: 1\nname: X\noutputs:\n  - a\nforbidden_actions:\n",  # empty forbidden_actions
        "  - dangling\nid: x\n",  # list item before any key
    ]
    for i, content in enumerate(bad):
        p = tmp_path / f"m{i}.yaml"
        p.write_text(content, encoding="utf-8")
        with pytest.raises(ModManifestError):
            load_manifest(p)
    # CRLF + BOM parse fine
    ok = tmp_path / "ok.yaml"
    ok.write_bytes("﻿id: x\r\nversion: 0.1.0\r\nname: X\r\noutputs:\r\n  - routing_hint\r\nforbidden_actions:\r\n  - write_canonical_decision\r\n".encode("utf-8"))
    assert load_manifest(ok).id == "x"


def test_run_mod_rejects_secret_in_input_metadata():
    # ADR-0014: run_mod defensively re-screens INPUT emissions. A secret in input
    # metadata (now preserved through normalize) must be rejected before evaluate runs.
    ref = SourceRef(source_id="osv", ref="vuln/1", url="https://example/v/1", kind="vulnerability")
    ev = SourceEvidence(source_ref=ref, excerpt="vuln summary", author="x")
    poisoned = AdapterEmission(source_id="osv", title="v", body="vuln summary", evidence=(ev,),
                               metadata={"leak": "AKIAIOSFODNN7EXAMPLE"})

    class _NeverEvaluated:
        id = "dependency-risk"
        version = "0.1.0"
        outputs = frozenset({"dependency_signal"})

        def evaluate(self, emissions):
            raise AssertionError("evaluate must not run on secret-bearing input")

    with pytest.raises(EmissionContractError):
        run_mod(_NeverEvaluated(), [poisoned], _manifest({"dependency_signal"}))


def test_all_manifests_representable():
    # F4: every shipped manifest's outputs are known + forbidden_actions ⊇ the EM-safe baseline.
    manifests = sorted(_MODS_DIR.glob("*/manifest.yaml"))
    assert len(manifests) == 13
    for path in manifests:
        m = load_manifest(path)
        assert m.outputs <= _KNOWN_OUTPUTS, f"{path}: unknown outputs {m.outputs - _KNOWN_OUTPUTS}"
        assert m.forbidden_actions >= _EM_SAFE_FORBIDDEN, f"{path}: missing {_EM_SAFE_FORBIDDEN - m.forbidden_actions}"
