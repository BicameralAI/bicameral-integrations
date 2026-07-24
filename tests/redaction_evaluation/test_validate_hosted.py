# SPDX-License-Identifier: MIT
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("hosted_validator", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load_module(
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validate_redaction_evaluation_hosted.py"
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    root = tmp_path
    artifacts = root / "artifacts" / "redaction-evaluation"
    source_manifest = root / "tests" / "redaction_evaluation" / "corpus-manifest.json"
    manifest = {"schema_version": 1, "corpus_id": "test", "description": "test", "records": []}
    _write_json(source_manifest, manifest)
    _write_json(artifacts / "corpus-manifest.json", manifest)

    gate_entry = {
        "candidate_id": "baseline",
        "passed": True,
        "pending_gate_ids": [],
        "gates": [
            {
                "gate_id": "receipt-contract-compatible",
                "status": "passed",
                "affected_record_ids": [],
                "evidence": {},
                "raw_values_included": False,
            }
        ],
    }
    matrix_entry = {
        "candidate_id": "baseline",
        "family": "baseline",
        "engine_version": "1",
        "packages": {},
        "models": {},
        "configuration_digest": "sha256:" + "1" * 64,
        "corpus_digest": "sha256:" + "2" * 64,
        "hard_gates_passed": True,
        "pending_gate_ids": [],
        "selection_eligible": True,
    }
    metric_entry = {
        "candidate_id": "baseline",
        "corpus_digest": matrix_entry["corpus_digest"],
    }

    _write_json(artifacts / "candidate-matrix.json", {"schema_version": 1, "candidates": [matrix_entry]})
    _write_json(artifacts / "hard-gates.json", {"schema_version": 1, "candidates": [gate_entry]})
    _write_json(artifacts / "metrics.json", {"schema_version": 1, "candidates": [metric_entry]})
    _write_json(
        artifacts / "candidate-results" / "baseline.json",
        {
            "schema_version": 1,
            "candidate_id": "baseline",
            "configuration_digest": matrix_entry["configuration_digest"],
            "corpus_digest": matrix_entry["corpus_digest"],
            "hard_gates": gate_entry,
        },
    )

    for name in (
        "benchmark-results.json",
        "candidate-research-matrix.json",
        "dependency-report.json",
        "environment.json",
        "license-report.json",
        "offline-proof.json",
        "vulnerability-report.json",
    ):
        _write_json(artifacts / name, {})
    (artifacts / "entity-results.csv").write_text("candidate_id\nbaseline\n", encoding="utf-8")
    (artifacts / "recommendation.md").write_text("Retain `baseline`.\n", encoding="utf-8")
    return root, matrix_entry, gate_entry


def test_valid_complete_artifacts_pass(tmp_path: Path) -> None:
    root, _, _ = _fixture(tmp_path)
    errors, receipt = MODULE.validate_repository(root)
    assert errors == []
    assert receipt["status"] == "passed"
    assert receipt["candidate_ids"] == ["baseline"]


def test_pending_gate_makes_candidate_ineligible(tmp_path: Path) -> None:
    root, matrix_entry, gate_entry = _fixture(tmp_path)
    gate_entry["gates"][0]["status"] = "pending"
    gate_entry["pending_gate_ids"] = ["receipt-contract-compatible"]
    gate_entry["passed"] = False
    matrix_entry["pending_gate_ids"] = ["receipt-contract-compatible"]
    matrix_entry["hard_gates_passed"] = False
    matrix_entry["selection_eligible"] = True

    artifacts = root / "artifacts" / "redaction-evaluation"
    _write_json(artifacts / "candidate-matrix.json", {"schema_version": 1, "candidates": [matrix_entry]})
    _write_json(artifacts / "hard-gates.json", {"schema_version": 1, "candidates": [gate_entry]})
    result_path = artifacts / "candidate-results" / "baseline.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["hard_gates"] = gate_entry
    _write_json(result_path, result)

    errors, _ = MODULE.validate_repository(root)
    assert any("selection_eligible must be false" in error for error in errors)


def test_aggregate_gate_drift_is_rejected(tmp_path: Path) -> None:
    root, _, gate_entry = _fixture(tmp_path)
    drifted = json.loads(json.dumps(gate_entry))
    drifted["gates"][0]["evidence"] = {"drifted": True}
    _write_json(
        root / "artifacts" / "redaction-evaluation" / "hard-gates.json",
        {"schema_version": 1, "candidates": [drifted]},
    )

    errors, _ = MODULE.validate_repository(root)
    assert any("aggregate hard gates differ" in error for error in errors)
