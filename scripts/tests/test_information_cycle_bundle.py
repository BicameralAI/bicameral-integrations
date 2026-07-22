# SPDX-License-Identifier: MIT
"""Information-cycle evidence bundle: negatives + deterministic regeneration."""

from __future__ import annotations

import copy
import importlib.util
import json
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


def _reseal(bundle: dict) -> dict:
    bundle["bundle_id"] = validator.bundle_id(bundle)
    return bundle


def _errors(bundle: dict) -> list[str]:
    return validator.semantic_errors(bundle)


def test_committed_bundle_is_valid() -> None:
    assert validator.validate_bundle(_BUNDLE_PATH) == []


def test_stage_ledger_is_the_exact_ordered_twenty() -> None:
    assert tuple(s["stage_id"] for s in _BUNDLE["stages"]) == validator.REQUIRED_STAGE_ORDER
    assert [s["sequence"] for s in _BUNDLE["stages"]] == list(range(1, 21))


def test_digest_chain_links_every_stage() -> None:
    anchor = ""
    for index, stage in enumerate(_BUNDLE["stages"]):
        if index > 0:
            assert stage["previous_stage"]["output_digest"] == anchor, stage["stage_id"]
        if "output" in stage:
            anchor = stage["output"]["aggregate_digest"]


def test_reordered_stages_fail() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][3], bundle["stages"][4] = bundle["stages"][4], bundle["stages"][3]
    assert any("reordered" in e or "missing required" in e for e in _errors(_reseal(bundle)))


def test_duplicate_stage_id_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][1]["stage_id"] = "raw_acquisition"
    assert any("duplicate" in e for e in _errors(_reseal(bundle)))


def test_missing_stage_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    del bundle["stages"][5]
    assert any("missing required stage" in e for e in _errors(_reseal(bundle)))


def test_broken_previous_link_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][6]["previous_stage"]["output_digest"] = "sha256:" + "0" * 64
    assert any("broken previous-stage digest link" in e for e in _errors(_reseal(bundle)))


def test_tampered_artifact_digest_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][0]["output"]["artifacts"][0]["digest"] = "sha256:" + "1" * 64
    assert any("digest mismatch" in e for e in _errors(_reseal(bundle)))


def test_incorrect_aggregate_digest_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][2]["output"]["aggregate_digest"] = "sha256:" + "2" * 64
    errors = _errors(_reseal(bundle))
    assert any("aggregate_digest incorrect" in e or "broken previous-stage" in e for e in errors)


def test_missing_artifact_on_disk_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][0]["output"]["artifacts"][0]["path"] = "ingest/evidence/does-not-exist.json"
    assert any("missing from disk" in e for e in _errors(_reseal(bundle)))


def test_unknown_status_and_class_fail_schema() -> None:
    schema = json.loads(
        (_REPO / "ingest" / "_schema" / "information-cycle-evidence-bundle.schema.json").read_text(encoding="utf-8")
    )
    from validate_connector_config import _check

    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][0]["status"] = "verified"
    assert any("verified" in e for e in _check(bundle, schema, "bundle"))

    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][0]["evidence_class"] = "production"
    assert any("production" in e for e in _check(bundle, schema, "bundle"))


def test_passed_after_unproven_upstream_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    gateway = bundle["stages"][14]
    assert gateway["stage_id"] == "gateway_negotiation"
    bot = bundle["stages"][15]
    bot["status"] = "passed"
    bot["evidence_class"] = "component"
    bot["transformation"] = {"name": "fabricated", "implementation": {"repository": "x/y", "path": "z"}}
    bot["output"] = bundle["stages"][13]["output"]
    bundle["unproven_downstream"] = [s["stage_id"] for s in bundle["stages"] if s["status"] == "unproven"]
    assert any("cannot claim passed after an upstream" in e for e in _errors(_reseal(bundle)))


def test_evidence_class_escalation_without_receipt_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][13]["evidence_class"] = "observed_live"
    assert any("receipt type" in e for e in _errors(_reseal(bundle)))


def test_unproven_stage_with_fabricated_output_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["stages"][14]["output"] = copy.deepcopy(bundle["stages"][13]["output"])
    assert any("fabricated output" in e for e in _errors(_reseal(bundle)))


def test_bundle_id_tamper_fails() -> None:
    bundle = copy.deepcopy(_BUNDLE)
    bundle["run_id"] = "edited-after-sealing"
    assert any("bundle_id does not match" in e for e in _errors(bundle))


def test_deterministic_regeneration(tmp_path: Path) -> None:
    """Same sanitized capture + same implementation => identical stage artifact
    digests and linkage; only the excluded timestamps and the recorded commit
    may differ across regeneration contexts."""
    regenerated = generator.build_bundle("local_directory/passive_import", tmp_path)
    for committed, fresh in zip(_BUNDLE["stages"], regenerated["stages"], strict=True):
        assert committed["stage_id"] == fresh["stage_id"]
        assert committed.get("output", {}).get("aggregate_digest") == fresh.get("output", {}).get("aggregate_digest"), committed["stage_id"]
        assert committed.get("previous_stage", {}).get("output_digest") == fresh.get("previous_stage", {}).get("output_digest")


def test_no_raw_sensitive_values_anywhere_in_the_bundle_tree() -> None:
    from adapter.core.sensitive import detect_sensitive

    root = _BUNDLE_PATH.parent
    for path in root.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert detect_sensitive(text) == [], path.name
        assert "@example.com" not in text or "[redacted:email]" in text
