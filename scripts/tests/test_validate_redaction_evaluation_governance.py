# SPDX-License-Identifier: MIT
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from scripts.validate_redaction_evaluation_governance import validate_repository

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_SOURCE = _REPO_ROOT / "tests" / "redaction_evaluation" / "schema"
_ZERO_HASH = "sha256:" + "0" * 64
_ZERO_SHA = "0" * 40


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _build_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(
        _SCHEMA_SOURCE,
        root / "tests" / "redaction_evaluation" / "schema",
    )
    return root


def _review() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "review_id": "redaction-review-v1",
        "reviewed_pr": {
            "repository": "BicameralAI/bicameral-integrations",
            "number": 300,
            "head_sha": _ZERO_SHA,
            "base_ref": "feat/alpha-ingest-real-data-redaction",
        },
        "parent_baseline": {
            "pr_number": 269,
            "head_sha": "fd69ff2742363b5d619bc073b8e8490c0f50733d",
        },
        "corpus_sha256": _ZERO_HASH,
        "artifact_bundle_sha256": _ZERO_HASH,
        "candidate_ids": ["bicameral-baseline"],
        "verdict": "owner_decision_ready",
        "checks": [
            {
                "check_id": "corpus-integrity",
                "status": "passed",
                "evidence_refs": ["artifact:corpus-manifest"],
                "affected_candidate_ids": [],
                "affected_record_ids": [],
                "raw_values_included": False,
            }
        ],
        "unresolved_discrepancies": [],
        "evidence_refs": ["artifact:evaluation-bundle"],
        "raw_values_included": False,
        "reviewed_at": "2026-07-23T22:00:00Z",
    }


def _decision(review_digest: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "decision_id": "redaction-backend-alpha-v1",
        "decision_owner": "Kevin Knapp",
        "status": "accepted",
        "outcome": "retain_baseline",
        "selected_candidate_id": None,
        "evidence_bindings": {
            "evaluation_repository": "BicameralAI/bicameral-integrations",
            "evaluation_pr_number": 300,
            "evaluation_head_sha": _ZERO_SHA,
            "parent_pr_269_head_sha": "fd69ff2742363b5d619bc073b8e8490c0f50733d",
            "corpus_sha256": _ZERO_HASH,
            "candidate_matrix_sha256": _ZERO_HASH,
            "hard_gates_sha256": _ZERO_HASH,
            "metrics_sha256": _ZERO_HASH,
            "benchmarks_sha256": _ZERO_HASH,
            "dependency_report_sha256": _ZERO_HASH,
            "license_report_sha256": _ZERO_HASH,
            "vulnerability_report_sha256": _ZERO_HASH,
            "adversarial_review_sha256": review_digest,
        },
        "eligible_candidates": ["bicameral-baseline"],
        "ineligible_candidates": [],
        "measured_summary": {
            "baseline_candidate_id": "bicameral-baseline",
            "recommended_candidate_id": "bicameral-baseline",
            "recommendation_confidence": "high",
            "score_summary": [
                {
                    "candidate_id": "bicameral-baseline",
                    "eligible": True,
                    "weighted_score": 80.0,
                }
            ],
            "material_tradeoffs": ["Baseline has lower contextual PII recall."],
        },
        "owner_judgment": "Retain the deterministic baseline for alpha.",
        "rationale": "No challenger provides enough measured benefit to justify migration.",
        "unresolved_uncertainty": [],
        "migration_disposition": "no_change",
        "migration_issue": None,
        "rollback_requirements": [],
        "architecture_update_required": False,
        "production_evidence_rebind_required": False,
        "release_authority_granted": False,
        "decided_at": "2026-07-23T22:05:00Z",
    }


def _write_valid_artifacts(root: Path) -> tuple[Path, Path]:
    artifact_root = root / "artifacts" / "redaction-evaluation"
    review_path = artifact_root / "adversarial-review.json"
    decision_path = artifact_root / "owner-decision.json"
    _write_json(review_path, _review())
    _write_json(decision_path, _decision(_sha256(review_path)))
    return review_path, decision_path


def test_schema_only_state_is_valid(tmp_path: Path) -> None:
    root = _build_root(tmp_path)
    assert validate_repository(root) == []


def test_valid_review_and_decision_are_accepted(tmp_path: Path) -> None:
    root = _build_root(tmp_path)
    _write_valid_artifacts(root)
    assert validate_repository(root) == []


def test_decision_ready_review_cannot_contain_failed_checks(tmp_path: Path) -> None:
    root = _build_root(tmp_path)
    review_path, decision_path = _write_valid_artifacts(root)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review["checks"][0]["status"] = "failed"
    _write_json(review_path, review)
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["evidence_bindings"]["adversarial_review_sha256"] = _sha256(review_path)
    _write_json(decision_path, decision)

    assert any("cannot contain failed checks" in error for error in validate_repository(root))


def test_accepted_decision_requires_review(tmp_path: Path) -> None:
    root = _build_root(tmp_path)
    decision_path = root / "artifacts" / "redaction-evaluation" / "owner-decision.json"
    _write_json(decision_path, _decision(_ZERO_HASH))

    assert any("requires adversarial review" in error for error in validate_repository(root))


def test_selected_candidate_must_be_eligible(tmp_path: Path) -> None:
    root = _build_root(tmp_path)
    review_path, decision_path = _write_valid_artifacts(root)
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["outcome"] = "select_candidate"
    decision["selected_candidate_id"] = "challenger"
    decision["migration_disposition"] = "implementation_issue_required"
    decision["migration_issue"] = "https://github.com/BicameralAI/bicameral-integrations/issues/999"
    decision["production_evidence_rebind_required"] = True
    decision["evidence_bindings"]["adversarial_review_sha256"] = _sha256(review_path)
    _write_json(decision_path, decision)

    assert any("selected candidate must be eligible" in error for error in validate_repository(root))


def test_review_digest_mismatch_is_rejected(tmp_path: Path) -> None:
    root = _build_root(tmp_path)
    _write_valid_artifacts(root)
    decision_path = root / "artifacts" / "redaction-evaluation" / "owner-decision.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["evidence_bindings"]["adversarial_review_sha256"] = _ZERO_HASH
    _write_json(decision_path, decision)

    assert any("review SHA-256 mismatch" in error for error in validate_repository(root))
