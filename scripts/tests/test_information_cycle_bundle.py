# SPDX-License-Identifier: MIT
"""Information-cycle evidence bundle: provenance, dual chains, raw-sample
policy, evidence classes, negatives, and deterministic regeneration."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
for extra in (str(_REPO), str(_REPO / "scripts")):
    if extra not in sys.path:
        sys.path.insert(0, extra)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


validator = _load("validate_information_cycle_bundle")
generator = _load("generate_information_cycle_bundle")

_BUNDLE_PATH = _REPO / "ingest" / "evidence" / "local_directory-passive_import" / "bundle.json"
_BUNDLE = json.loads(_BUNDLE_PATH.read_text(encoding="utf-8"))
_HEAD = subprocess.run(
    ["git", "-C", str(_REPO), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
).stdout.strip()


def _reseal(bundle: dict) -> dict:
    for index, stage in enumerate(bundle["stages"]):
        if index > 0:
            stage["previous_stage_record"] = {
                "stage_id": bundle["stages"][index - 1]["stage_id"],
                "stage_record_digest": bundle["stages"][index - 1]["stage_record_digest"],
            }
        stage["stage_record_digest"] = validator.stage_record_digest(stage)
    bundle["bundle_id"] = validator.bundle_id(bundle)
    return bundle


def _errors(bundle: dict) -> list[str]:
    return validator.semantic_errors(bundle, head=_HEAD)


def test_committed_bundle_is_valid() -> None:
    assert validator.validate_bundle(_BUNDLE_PATH, head=_HEAD) == []


def test_stage_ledger_is_the_exact_ordered_twenty() -> None:
    assert tuple(s["stage_id"] for s in _BUNDLE["stages"]) == validator.REQUIRED_STAGE_ORDER
    assert [s["sequence"] for s in _BUNDLE["stages"]] == list(range(1, 21))


# ---------------------------------------------------------------------------
# Implementation provenance
# ---------------------------------------------------------------------------


def test_reviewed_commit_is_ancestor_and_blobs_match() -> None:
    prov = _BUNDLE["implementation_provenance"]
    assert validator.git_is_ancestor(_REPO, prov["reviewed_commit"], _HEAD)
    for component in prov["components"]:
        at_reviewed = validator.git_blob_digest(_REPO, prov["reviewed_commit"], component["path"])
        assert at_reviewed == component["blob_sha256"], component["path"]
        assert validator.file_digest(_REPO / component["path"]) == component["blob_sha256"]


def test_non_ancestor_reviewed_commit_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["implementation_provenance"]["reviewed_commit"] = "a" * 40
    assert any("not an ancestor" in e for e in _errors(_reseal(bundle)))


def test_missing_implementation_path_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["implementation_provenance"]["components"][0]["path"] = "scripts/does-not-exist.py"
    errors = _errors(_reseal(bundle))
    assert any("absent at reviewed_commit" in e for e in errors)


def test_stale_blob_digest_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["implementation_provenance"]["components"][0]["blob_sha256"] = "sha256:" + "3" * 64
    errors = _errors(_reseal(bundle))
    assert any("stale" in e or "changed after" in e for e in errors)


def test_stage_citing_unregistered_implementation_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][3]["transformation"]["implementation"]["path"] = "scripts/unregistered.py"
    assert any("not registered in implementation_provenance" in e for e in _errors(_reseal(bundle)))


def test_exact_head_receipt_recomputes() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        receipt = validator.emit_head_receipt(_BUNDLE, _REPO, Path(tmp) / "receipt.json")
    assert receipt["head_commit"] == _HEAD
    assert receipt["receipt_id"].startswith("sha256:")
    for component in receipt["components"]:
        assert component["blob_sha256"].startswith("sha256:")


# ---------------------------------------------------------------------------
# Stage-record chain vs transformation-output lineage
# ---------------------------------------------------------------------------


def test_record_chain_links_every_stage_including_unproven() -> None:
    for index, stage in enumerate(_BUNDLE["stages"]):
        assert stage["stage_record_digest"] == validator.stage_record_digest(stage)
        if index > 0:
            link = stage["previous_stage_record"]
            assert link["stage_id"] == _BUNDLE["stages"][index - 1]["stage_id"]
            assert link["stage_record_digest"] == _BUNDLE["stages"][index - 1]["stage_record_digest"]


def test_altered_unproven_reason_breaks_the_record_chain() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][15]["unproven"]["reason"] = "tampered"
    # NOT resealed: tampering without recomputing the chain must be caught.
    errors = _errors(bundle)
    assert any("stage_record_digest does not match" in e for e in errors)


def test_altered_authority_breaks_the_record_chain() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][14]["authority"]["owner"] = "tampered"
    assert any("stage_record_digest does not match" in e for e in _errors(bundle))


def test_broken_record_link_fails_even_after_reseal_of_one_stage() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][7]["previous_stage_record"]["stage_record_digest"] = "sha256:" + "4" * 64
    errors = validator.semantic_errors(bundle, head=_HEAD)
    assert any("broken stage-record chain link" in e for e in errors)


def test_output_dependency_cites_real_producers_with_matching_digests() -> None:
    outputs = {
        s["stage_id"]: s["output"]["aggregate_digest"]
        for s in _BUNDLE["stages"]
        if "output" in s
    }
    for stage in _BUNDLE["stages"]:
        for dep in stage.get("depends_on_outputs", []):
            if "output_digest" in dep:
                assert dep["stage_id"] in outputs
                assert dep["output_digest"] == outputs[dep["stage_id"]]
            else:
                assert dep["status"] == "missing" and dep["required_output"]
                assert dep["stage_id"] not in outputs


def test_output_less_stage_cannot_be_cited_as_emitting_a_digest() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bot = bundle["stages"][15]
    assert bot["stage_id"] == "bot_acceptance"
    bot["depends_on_outputs"] = [
        {"stage_id": "gateway_negotiation", "output_digest": "sha256:" + "5" * 64}
    ]
    assert any("produced no output artifacts" in e for e in _errors(_reseal(bundle)))


def test_missing_future_prerequisite_stays_explicit() -> None:
    bot = next(s for s in _BUNDLE["stages"] if s["stage_id"] == "bot_acceptance")
    missing = [d for d in bot["depends_on_outputs"] if d.get("status") == "missing"]
    assert missing and missing[0]["stage_id"] == "gateway_negotiation"
    held = [d for d in bot["depends_on_outputs"] if "output_digest" in d]
    assert held and held[0]["stage_id"] == "external_ingest_envelope"


# ---------------------------------------------------------------------------
# Raw-sample safety (stage-aware; NOT "no PII anywhere")
# ---------------------------------------------------------------------------


def test_approved_raw_email_exists_only_in_the_raw_stage_artifact() -> None:
    policy = _BUNDLE["raw_sample_policy"]
    assert policy["repository_owned"] and policy["public_content"]
    permitted = {p["value_digest"]: p["allowed_stage_ids"] for p in policy["permitted_raw_values"]}
    assert permitted, "the approved sample declares its permitted raw values"

    raw_stage = _BUNDLE["stages"][0]
    raw_artifact = _REPO / raw_stage["output"]["artifacts"][0]["path"]
    raw_text = raw_artifact.read_text(encoding="utf-8")
    found = set(validator._EMAIL_RE.findall(raw_text))
    assert found, "the raw artifact intentionally shows what entered"
    for email in found:
        digest = validator.value_digest(email)
        assert digest in permitted
        assert permitted[digest] == ["raw_acquisition"]

    # Every LATER stage's artifacts exclude the raw value.
    for stage in _BUNDLE["stages"][1:]:
        for artifact in stage.get("output", {}).get("artifacts", []):
            text = (_REPO / artifact["path"]).read_text(encoding="utf-8")
            for email in found:
                assert email not in text, (stage["stage_id"], artifact["path"])


def test_unknown_email_in_an_artifact_fails(tmp_path: Path) -> None:
    bundle = copy.deepcopy(_BUNDLE)
    rogue = tmp_path / "rogue.json"
    rogue.write_text(json.dumps({"note": "mail intruder@example.com now"}), encoding="utf-8")
    stage = bundle["stages"][3]
    stage["output"]["artifacts"][0] = {
        "path": str(rogue),
        "digest": validator.file_digest(rogue),
        "media_type": "application/json",
    }
    stage["output"]["aggregate_digest"] = validator.aggregate_digest(stage["output"]["artifacts"])
    errors = _errors(_reseal(bundle))
    assert any("unknown email" in e for e in errors)


def test_permitted_value_outside_allowed_stage_fails(tmp_path: Path) -> None:
    bundle = copy.deepcopy(_BUNDLE)
    raw_email_digests = [p["value_digest"] for p in bundle["raw_sample_policy"]["permitted_raw_values"]]
    raw_text = (_REPO / bundle["stages"][0]["output"]["artifacts"][0]["path"]).read_text(encoding="utf-8")
    email = sorted(set(validator._EMAIL_RE.findall(raw_text)))[0]
    assert validator.value_digest(email) in raw_email_digests

    leak = tmp_path / "leak.json"
    leak.write_text(json.dumps({"leaked": email}), encoding="utf-8")
    stage = bundle["stages"][4]
    stage["output"]["artifacts"][0] = {
        "path": str(leak),
        "digest": validator.file_digest(leak),
        "media_type": "application/json",
    }
    stage["output"]["aggregate_digest"] = validator.aggregate_digest(stage["output"]["artifacts"])
    errors = _errors(_reseal(bundle))
    assert any("outside its allowed stage" in e for e in errors)


def test_secret_phi_pan_scans_enforced_on_artifacts() -> None:
    from adapter.core.sensitive import detect_sensitive

    for stage in _BUNDLE["stages"]:
        for artifact in stage.get("output", {}).get("artifacts", []):
            assert detect_sensitive((_REPO / artifact["path"]).read_text(encoding="utf-8")) == []


def test_raw_values_never_in_failures_or_warnings_or_bundle_metadata() -> None:
    text = json.dumps(_BUNDLE, sort_keys=True)
    assert not validator._EMAIL_RE.search(text)


# ---------------------------------------------------------------------------
# Evidence classes: held vs required
# ---------------------------------------------------------------------------


def test_unproven_stages_hold_none_and_declare_required_class() -> None:
    for stage in _BUNDLE["stages"]:
        if stage["status"] == "unproven":
            assert stage["evidence_class"] == "none"
            assert stage["required_evidence_class"] in (
                "component", "observed_live", "terminal_product", "human_accepted",
            )
        if stage["status"] == "passed":
            assert stage["evidence_class"] == "component"


def test_unproven_with_held_class_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][15]["evidence_class"] = "observed_live"
    assert any("holds no evidence" in e for e in _errors(_reseal(bundle)))


def test_passed_with_none_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][3]["evidence_class"] = "none"
    assert any("cannot hold evidence_class none" in e for e in _errors(_reseal(bundle)))


def test_missing_required_class_on_unproven_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    del bundle["stages"][16]["required_evidence_class"]
    assert any("required_evidence_class" in e for e in _errors(_reseal(bundle)))


def test_future_requirements_never_escalate_bundle_class() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["evidence_class"] = "observed_live"
    assert any("strongest ACTUALLY HELD" in e for e in _errors(_reseal(bundle)))


def test_human_accepted_claim_requires_acceptance_receipt() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][13]["evidence_class"] = "human_accepted"
    errors = _errors(_reseal(bundle))
    assert any("receipt" in e for e in errors)


# ---------------------------------------------------------------------------
# Regeneration + core negatives carried forward
# ---------------------------------------------------------------------------


def test_deterministic_regeneration(tmp_path: Path) -> None:
    regenerated = generator.build_bundle(
        "local_directory/passive_import",
        tmp_path,
        reviewed_commit=_BUNDLE["implementation_provenance"]["reviewed_commit"],
    )
    for committed, fresh in zip(_BUNDLE["stages"], regenerated["stages"], strict=True):
        assert committed["stage_id"] == fresh["stage_id"]
        assert committed.get("output", {}).get("aggregate_digest") == fresh.get("output", {}).get("aggregate_digest"), committed["stage_id"]
        assert committed["stage_record_digest"] == fresh["stage_record_digest"], committed["stage_id"]
    assert regenerated["bundle_id"] == _BUNDLE["bundle_id"]


def test_reordered_or_missing_stages_fail() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][3], bundle["stages"][4] = bundle["stages"][4], bundle["stages"][3]
    assert _errors(bundle)

    bundle = copy.deepcopy(_BUNDLE)
    del bundle["stages"][5]
    assert any("missing required stage" in e for e in _errors(bundle))


def test_tampered_artifact_digest_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][0]["output"]["artifacts"][0]["digest"] = "sha256:" + "1" * 64
    assert any("digest mismatch" in e for e in _errors(_reseal(bundle)))


def test_unproven_stage_with_fabricated_output_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][14]["output"] = copy.deepcopy(bundle["stages"][13]["output"])
    assert any("fabricated output" in e for e in _errors(_reseal(bundle)))


def test_bundle_id_tamper_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["run_id"] = "edited-after-sealing"
    assert any("bundle_id does not match" in e for e in _errors(bundle))
