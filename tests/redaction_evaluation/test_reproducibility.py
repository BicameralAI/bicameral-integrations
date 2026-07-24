# SPDX-License-Identifier: MIT
"""Reproducibility, scoring, binding, and review-artifact tests (ADR-0020).

Runs without any heavy candidate dependency: the evaluation-input digest is
computed from statically pinned backend identities (no ``initialize()``, no
model loads), scoring operates on synthetic artifact documents, and the
review generator is exercised against a minimal synthetic artifact tree.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.redaction_evaluation import input_digest, review  # noqa: E402
from runtime.redaction_evaluation.policy import RedactionPolicy  # noqa: E402
from runtime.redaction_evaluation.scoring import (  # noqa: E402
    compute_weighted_scores,
    derive_gate_aggregate,
)

SCHEMA_DIR = REPO_ROOT / "tests" / "redaction_evaluation" / "schema"


def _load_script() -> ModuleType:
    path = REPO_ROOT / "scripts" / "evaluate_redaction_backends.py"
    spec = importlib.util.spec_from_file_location("evaluate_redaction_backends", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT = _load_script()


def _write_text(path: Path, text: str) -> None:
    """LF-pinned write: artifact comparisons in the harness are byte-exact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# Evaluation-input digest
# ---------------------------------------------------------------------------


def _fixture_repo(tmp_path: Path) -> Path:
    """Minimal synthetic corpus tree: 1 input, 1 expected, real schemas."""

    root = tmp_path / "repo"
    corpus_dir = root / "tests" / "redaction_evaluation" / "corpus"
    expected_dir = root / "tests" / "redaction_evaluation" / "expected"
    schema_dir = root / "tests" / "redaction_evaluation" / "schema"
    corpus_dir.mkdir(parents=True)
    expected_dir.mkdir(parents=True)
    schema_dir.mkdir(parents=True)
    for schema in sorted(SCHEMA_DIR.glob("*.json")):
        shutil.copyfile(schema, schema_dir / schema.name)
    (corpus_dir / "r1.json").write_text('{"observation": {}}\n', encoding="utf-8")
    (expected_dir / "r1.json").write_text(
        '{"record_id": "r1"}\n', encoding="utf-8"
    )
    _write_json(
        root / "tests" / "redaction_evaluation" / "corpus-manifest.json",
        {
            "schema_version": 1,
            "corpus_id": "fixture",
            "description": "fixture",
            "records": [
                {
                    "record_id": "r1",
                    "input_path": "tests/redaction_evaluation/corpus/r1.json",
                    "expected_path": "tests/redaction_evaluation/expected/r1.json",
                    "input_sha256": "sha256:" + "0" * 64,
                    "expected_sha256": "sha256:" + "0" * 64,
                    "source_shape": "plain_text",
                    "classes": ["positive_detection"],
                }
            ],
        },
    )
    return root


def _digest_of(root: Path) -> str:
    document = input_digest.compute_evaluation_input_digest(root)
    value = document["evaluation_input_sha256"]
    assert isinstance(value, str) and value.startswith("sha256:")
    return value


def test_input_digest_stable_for_unchanged_tree(tmp_path: Path) -> None:
    root = _fixture_repo(tmp_path)
    assert _digest_of(root) == _digest_of(root)


def test_input_digest_changes_on_input_byte(tmp_path: Path) -> None:
    root = _fixture_repo(tmp_path)
    before = _digest_of(root)
    target = root / "tests" / "redaction_evaluation" / "corpus" / "r1.json"
    target.write_bytes(target.read_bytes() + b" ")
    assert _digest_of(root) != before


def test_input_digest_changes_on_expected_byte(tmp_path: Path) -> None:
    root = _fixture_repo(tmp_path)
    before = _digest_of(root)
    target = root / "tests" / "redaction_evaluation" / "expected" / "r1.json"
    target.write_bytes(target.read_bytes() + b" ")
    assert _digest_of(root) != before


def test_input_digest_changes_on_schema_byte(tmp_path: Path) -> None:
    root = _fixture_repo(tmp_path)
    before = _digest_of(root)
    target = (
        root
        / "tests"
        / "redaction_evaluation"
        / "schema"
        / "adversarial-review.schema.json"
    )
    target.write_bytes(target.read_bytes() + b"\n")
    assert _digest_of(root) != before


def test_input_digest_changes_on_policy_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _fixture_repo(tmp_path)
    before = _digest_of(root)
    monkeypatch.setattr(
        input_digest,
        "RedactionPolicy",
        lambda: RedactionPolicy(policy_id="mutated-policy-v0"),
    )
    assert _digest_of(root) != before


def test_input_digest_binds_candidate_configurations(tmp_path: Path) -> None:
    root = _fixture_repo(tmp_path)
    document = input_digest.compute_evaluation_input_digest(root)
    bound = document["bound"]
    configurations = bound["candidate_configurations"]
    identities = bound["pinned_identities"]
    for candidate_id in (
        "bicameral-stdlib-v1",
        "presidio-spacy-lg-v1",
        "presidio-gliner-pii-v1",
        "datafog-regex-v1",
    ):
        assert configurations[candidate_id].startswith("sha256:")
        assert set(identities[candidate_id]) == {"packages", "models"}


# ---------------------------------------------------------------------------
# Weighted scoring
# ---------------------------------------------------------------------------


def _metrics_doc(f2: float = 0.8) -> dict[str, Any]:
    def candidate(candidate_id: str, candidate_f2: float) -> dict[str, Any]:
        return {
            "candidate_id": candidate_id,
            "totals": {"f2": candidate_f2, "precision": 0.9, "recall": 0.8},
            "preservation": {
                "destructive_false_positives": 0,
                "clean_records_modified": 0,
                "protected_field_mutations": 0,
                "decision_preservation": {"pass_ratio": 1.0},
            },
            "security": {
                "post_screen_escapes": 0,
                "repeated_output_mismatches": 0,
                "expected_outcome_agreement": {"records": 10, "matches": 10},
            },
        }

    return {
        "schema_version": 1,
        "candidates": [candidate("cand-a", f2), candidate("cand-b", 0.5)],
    }


def _gates_doc() -> dict[str, Any]:
    return {
        "candidates": [
            {
                "candidate_id": "cand-a",
                "gates": [{"gate_id": "g1", "status": "passed"}],
            },
            {
                "candidate_id": "cand-b",
                "gates": [{"gate_id": "g1", "status": "pending"}],
            },
        ]
    }


def _bench_doc() -> dict[str, Any]:
    def candidate(latency: float, byte_total: int, cold: float) -> dict[str, Any]:
        return {
            "warm_latency_ms": {"medium": {"p95": latency}},
            "package_bytes": {"total_bytes": byte_total},
            "model_bytes": {"total_bytes": 0},
            "cold_initialization": {"median_seconds": cold},
        }

    return {
        "candidates": {
            "cand-a": candidate(2.0, 1000, 0.5),
            "cand-b": candidate(4.0, 2000, 1.0),
        }
    }


def _memory_doc() -> dict[str, Any]:
    return {
        "candidates": [
            {"candidate_id": "cand-a", "peak_bytes": 1000},
            {"candidate_id": "cand-b", "peak_bytes": 2000},
        ]
    }


def test_weighted_scores_are_deterministic() -> None:
    first = compute_weighted_scores(
        _metrics_doc(), _gates_doc(), _bench_doc(), _memory_doc()
    )
    second = compute_weighted_scores(
        _metrics_doc(), _gates_doc(), _bench_doc(), _memory_doc()
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["advisory"] is True
    by_id = {entry["candidate_id"]: entry for entry in first["candidates"]}
    assert by_id["cand-a"]["aggregate_state"] == "passed"
    assert by_id["cand-a"]["selection_eligible"] is True
    assert by_id["cand-b"]["aggregate_state"] == "pending"
    assert by_id["cand-b"]["selection_eligible"] is False
    # cand-a is best on every performance axis.
    assert by_id["cand-a"]["scores"]["performance_resource"] == 10.0


def test_weighted_scores_change_when_a_metric_changes() -> None:
    base = compute_weighted_scores(
        _metrics_doc(f2=0.8), _gates_doc(), _bench_doc(), _memory_doc()
    )
    changed = compute_weighted_scores(
        _metrics_doc(f2=0.9), _gates_doc(), _bench_doc(), _memory_doc()
    )
    base_total = base["candidates"][0]["total"]
    changed_total = changed["candidates"][0]["total"]
    assert base["candidates"][0]["candidate_id"] == "cand-a"
    assert changed_total != base_total
    assert changed_total - base_total == pytest.approx(3.0)


def test_derive_gate_aggregate_is_fail_closed() -> None:
    assert derive_gate_aggregate([]) == ("failed", False, [], [])
    state, passed, pending, failed = derive_gate_aggregate(
        [
            {"gate_id": "a", "status": "passed"},
            {"gate_id": "b", "status": "pending"},
            {"gate_id": "c", "status": "bogus"},
        ]
    )
    assert (state, passed) == ("failed", False)
    assert pending == ["b"]
    assert failed == ["c"]


# ---------------------------------------------------------------------------
# Artifact-manifest drift detection
# ---------------------------------------------------------------------------


def _stub_artifact_dir(tmp_path: Path) -> Path:
    out_dir = tmp_path / "artifacts"
    out_dir.mkdir()
    for name in SCRIPT.MANIFEST_ARTIFACTS:
        _write_text(out_dir / name, f"stub: {name}\n")
    _write_json(
        out_dir / "candidate-results" / "cand-a.json", {"candidate_id": "cand-a"}
    )
    return out_dir


def test_artifact_manifest_detects_hand_edits(tmp_path: Path) -> None:
    out_dir = _stub_artifact_dir(tmp_path)
    _write_json(
        out_dir / "artifact-manifest.json",
        SCRIPT._artifact_manifest_document(out_dir),
    )
    assert SCRIPT._manifest_drift_errors(out_dir) == []
    _write_text(out_dir / "benchmark-results.json", "hand-edited benchmark\n")
    errors = SCRIPT._manifest_drift_errors(out_dir)
    assert errors and any("benchmark-results.json" in error for error in errors)


def test_artifact_manifest_requires_every_bound_artifact(tmp_path: Path) -> None:
    out_dir = _stub_artifact_dir(tmp_path)
    (out_dir / "memory-isolated.json").unlink()
    with pytest.raises(RuntimeError, match="memory-isolated.json"):
        SCRIPT._artifact_manifest_document(out_dir)


# ---------------------------------------------------------------------------
# Recommendation machine bindings
# ---------------------------------------------------------------------------


def _bindings() -> dict[str, Any]:
    return {
        "evaluation_input_sha256": "sha256:" + "1" * 64,
        "corpus_sha256": "sha256:" + "2" * 64,
        "candidates": [
            {
                "candidate_id": "cand-a",
                "configuration_digest": "sha256:" + "3" * 64,
                "aggregate_state": "passed",
                "selection_eligible": True,
                "f2": 0.8,
                "recall": 0.8,
                "precision": 0.9,
                "weighted_total": 80.0,
            }
        ],
        "artifact_sha256": {
            "metrics.json": "sha256:" + "4" * 64,
            "hard-gates.json": "sha256:" + "5" * 64,
            "weighted-scores.json": "sha256:" + "6" * 64,
        },
    }


def test_bindings_roundtrip_ok() -> None:
    bindings = _bindings()
    text = review.replace_bindings_block("# Recommendation\n\ncand-a prose.\n", bindings)
    assert review.parse_recommendation_bindings(text) == bindings
    assert review.verify_recommendation_bindings(text, bindings) == []
    # In-place replacement leaves the prose untouched and swaps only values.
    updated = dict(bindings, corpus_sha256="sha256:" + "7" * 64)
    text_two = review.replace_bindings_block(text, updated)
    assert review.parse_recommendation_bindings(text_two) == updated
    assert text_two.count("```json redaction-recommendation-bindings") == 1
    assert "cand-a prose." in review.strip_bindings_block(text_two)


def test_bindings_missing_block_is_an_error() -> None:
    with pytest.raises(ValueError, match="missing"):
        review.parse_recommendation_bindings("# Recommendation\n\nno block here\n")
    errors = review.verify_recommendation_bindings("no block\n", _bindings())
    assert errors and "missing" in errors[0]


def test_bindings_value_drift_is_an_error() -> None:
    bindings = _bindings()
    text = review.replace_bindings_block("# Recommendation\n", bindings)
    drifted = dict(bindings, evaluation_input_sha256="sha256:" + "9" * 64)
    errors = review.verify_recommendation_bindings(text, drifted)
    assert errors and any("evaluation_input_sha256" in error for error in errors)


# ---------------------------------------------------------------------------
# Adversarial-review generation
# ---------------------------------------------------------------------------

_HEAD_SHA = "ab" * 20


def _review_artifact_dir(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Synthetic, internally consistent artifact set plus regenerated texts."""

    out_dir = tmp_path / "artifacts"
    gates = [
        {"gate_id": "no-raw-leakage", "status": "passed"},
        {"gate_id": "deterministic-output", "status": "passed"},
        {"gate_id": "receipt-contract-compatible", "status": "passed"},
        {"gate_id": "license-compatible", "status": "pending"},
    ]
    state, passed, pending, failed = derive_gate_aggregate(gates)
    hard_gates = {
        "schema_version": 1,
        "candidates": [
            {
                "candidate_id": "cand-a",
                "aggregate_state": state,
                "passed": passed,
                "pending_gate_ids": pending,
                "failed_gate_ids": failed,
                "gates": gates,
            }
        ],
    }
    matrix = {
        "schema_version": 1,
        "candidates": [
            {
                "candidate_id": "cand-a",
                "corpus_digest": "sha256:" + "2" * 64,
                "configuration_digest": "sha256:" + "3" * 64,
                "aggregate_state": state,
                "hard_gates_passed": passed,
                "pending_gate_ids": pending,
                "selection_eligible": passed,
            }
        ],
    }
    documents: dict[str, Any] = {
        "hard-gates.json": hard_gates,
        "candidate-matrix.json": matrix,
        "metrics.json": {"schema_version": 1, "candidates": []},
        "weighted-scores.json": {"schema_version": 1, "candidates": []},
        "evaluation-input.json": {
            "schema_version": 1,
            "evaluation_input_sha256": "sha256:" + "1" * 64,
        },
        "offline-proof.json": {
            "candidates": [
                {"candidate_id": "cand-a", "passed": True, "attempted_connections": []}
            ]
        },
        "artifact-manifest.json": {"schema_version": 1, "artifacts": {}},
    }
    regenerated: dict[str, str] = {}
    for name, value in documents.items():
        text = json.dumps(value, indent=2, sort_keys=True) + "\n"
        _write_text(out_dir / name, text)
        regenerated[name] = text
    csv_text = "candidate_id\ncand-a\n"
    _write_text(out_dir / "entity-results.csv", csv_text)
    regenerated["entity-results.csv"] = csv_text
    _write_json(
        out_dir / "candidate-results" / "cand-a.json",
        {
            "candidate_id": "cand-a",
            "determinism": {"mismatched_record_ids": []},
            "hard_gates": hard_gates["candidates"][0],
        },
    )
    return out_dir, regenerated


def test_review_document_validates_against_real_schema(tmp_path: Path) -> None:
    out_dir, regenerated = _review_artifact_dir(tmp_path)
    checks = review.run_review_checks(
        out_dir, corpus_errors=[], regenerated=regenerated, binding_errors=[]
    )
    assert {check["check_id"] for check in checks} >= {
        "corpus-digests-verified",
        "aggregates-reproduce",
        "artifact-manifest-clean",
        "recommendation-bindings-verified",
        "eligibility-consistency",
        "hard-gate-states-recorded",
        "determinism-clean",
        "offline-proof-clean",
        "no-raw-leakage-gate",
        "receipt-validation-gate",
        "weighted-scores-reproduce",
        "external-verdicts-merged",
    }
    assert all(check["status"] == "passed" for check in checks)
    document = review.build_adversarial_review(
        out_dir,
        pr_number=291,
        head_sha=_HEAD_SHA,
        base_ref="main",
        reviewed_at="2026-07-24T00:00:00Z",
        checks=checks,
    )
    # build_adversarial_review schema-validates internally; assert semantics.
    assert document["verdict"] == "owner_decision_ready"
    assert document["review_id"] == f"adr-0020-exact-head-review-{_HEAD_SHA[:12]}"
    discrepancy_ids = {
        item["discrepancy_id"] for item in document["unresolved_discrepancies"]
    }
    assert "license-review-pending-cand-a" in discrepancy_ids
    assert all(
        item["severity"] != "blocker"
        for item in document["unresolved_discrepancies"]
    )


def test_review_failed_check_produces_blocker_verdict(tmp_path: Path) -> None:
    out_dir, regenerated = _review_artifact_dir(tmp_path)
    # A hand-edited artifact: committed metrics no longer match regenerated.
    _write_text(out_dir / "metrics.json", "tampered\n")
    checks = review.run_review_checks(
        out_dir, corpus_errors=[], regenerated=regenerated, binding_errors=[]
    )
    by_id = {check["check_id"]: check for check in checks}
    assert by_id["aggregates-reproduce"]["status"] == "failed"
    document = review.build_adversarial_review(
        out_dir,
        pr_number=291,
        head_sha=_HEAD_SHA,
        base_ref="main",
        reviewed_at="2026-07-24T00:00:00Z",
        checks=checks,
    )
    assert document["verdict"] == "not_reviewable"
    assert any(
        item["severity"] == "blocker"
        for item in document["unresolved_discrepancies"]
    )


def test_review_requires_explicit_reviewed_at(tmp_path: Path) -> None:
    out_dir, regenerated = _review_artifact_dir(tmp_path)
    checks = review.run_review_checks(
        out_dir, corpus_errors=[], regenerated=regenerated, binding_errors=[]
    )
    with pytest.raises(ValueError, match="reviewed_at"):
        review.build_adversarial_review(
            out_dir,
            pr_number=291,
            head_sha=_HEAD_SHA,
            base_ref="main",
            reviewed_at="not-a-timestamp",
            checks=checks,
        )


# ---------------------------------------------------------------------------
# External-verdict merge
# ---------------------------------------------------------------------------


def test_merge_candidate_gates_folds_external_verdicts() -> None:
    block = {
        "candidate_id": "cand-a",
        "passed": True,
        "pending_gate_ids": ["license-compatible", "no-undeclared-network"],
        "gates": [
            {"gate_id": "no-undeclared-network", "status": "pending"},
            {"gate_id": "license-compatible", "status": "pending"},
            {"gate_id": "no-raw-leakage", "status": "passed"},
        ],
    }
    merged = SCRIPT._merge_candidate_gates(block, True, None)
    statuses = {gate["gate_id"]: gate["status"] for gate in merged["gates"]}
    assert statuses["no-undeclared-network"] == "passed"
    # review_required stays an honest pending gate, never silently passed.
    assert statuses["license-compatible"] == "pending"
    assert merged["aggregate_state"] == "pending"
    assert merged["passed"] is False
    assert merged["pending_gate_ids"] == ["license-compatible"]
    assert merged["failed_gate_ids"] == []
    # Idempotent: re-applying the merge changes nothing.
    assert SCRIPT._merge_candidate_gates(merged, True, None) == merged
    # A failing license verdict fails the gate and the aggregate.
    failed = SCRIPT._merge_candidate_gates(block, True, False)
    assert failed["aggregate_state"] == "failed"
    assert failed["failed_gate_ids"] == ["license-compatible"]
