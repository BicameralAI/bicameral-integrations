# SPDX-License-Identifier: MIT
"""Validate committed ADR-0020 evaluation evidence for hosted stacked-PR checks.

This gate is intentionally model-free. It does not rerun detector benchmarks. It
checks that committed artifacts are complete, internally consistent, exact-head
bound, and honest about pending or failed hard gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_ARTIFACT_DIR = Path("artifacts/redaction-evaluation")
_CANDIDATE_RESULTS_DIR = _ARTIFACT_DIR / "candidate-results"
_SOURCE_MANIFEST = Path("tests/redaction_evaluation/corpus-manifest.json")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_HEAD_RE = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_GATE_STATUSES = {"passed", "pending", "failed"}

_REQUIRED_JSON = (
    "benchmark-results.json",
    "candidate-matrix.json",
    "candidate-research-matrix.json",
    "corpus-manifest.json",
    "dependency-report.json",
    "environment.json",
    "hard-gates.json",
    "license-report.json",
    "metrics.json",
    "offline-proof.json",
    "vulnerability-report.json",
)
_REQUIRED_TEXT = ("entity-results.csv", "recommendation.md")


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant is forbidden: {value}")


def _load_json(path: Path, label: str, errors: list[str]) -> Any | None:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_constant,
        )
    except FileNotFoundError:
        errors.append(f"{label}: file not found: {path}")
    except UnicodeDecodeError:
        errors.append(f"{label}: file is not valid UTF-8: {path}")
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label}: file is not strict JSON: {path}")
    return None


def _sha256_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _candidate_map(
    value: Any,
    label: str,
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or not isinstance(value.get("candidates"), list):
        errors.append(f"{label}: expected an object with a candidates array")
        return {}
    result: dict[str, dict[str, Any]] = {}
    for index, candidate in enumerate(value["candidates"]):
        if not isinstance(candidate, dict):
            errors.append(f"{label}: candidates[{index}] is not an object")
            continue
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            errors.append(f"{label}: candidates[{index}] has no candidate_id")
            continue
        if candidate_id in result:
            errors.append(f"{label}: duplicate candidate_id: {candidate_id}")
            continue
        result[candidate_id] = candidate
    return result


def _git_head(root: Path, errors: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        errors.append("git: unable to resolve checkout HEAD")
        return None
    head = completed.stdout.strip().lower()
    if not _HEAD_RE.fullmatch(head):
        errors.append(f"git: invalid checkout HEAD: {head!r}")
        return None
    return head


def validate_repository(
    root: Path = _ROOT,
    *,
    expected_head: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    root = root.resolve()
    errors: list[str] = []
    artifact_root = root / _ARTIFACT_DIR

    required_paths = [artifact_root / name for name in (*_REQUIRED_JSON, *_REQUIRED_TEXT)]
    for path in required_paths:
        if not path.is_file():
            errors.append(f"required artifact missing: {path.relative_to(root).as_posix()}")

    current_head = _git_head(root, errors) if expected_head is not None else None
    if expected_head is not None:
        normalized = expected_head.strip().lower()
        if not _HEAD_RE.fullmatch(normalized):
            errors.append("expected head must be a full 40-character lowercase SHA")
        elif current_head is not None and current_head != normalized:
            errors.append(
                f"exact-head mismatch: expected {normalized}, checkout is {current_head}"
            )

    documents: dict[str, Any] = {}
    for name in _REQUIRED_JSON:
        path = artifact_root / name
        if path.is_file():
            documents[name] = _load_json(path, name, errors)

    source_manifest = root / _SOURCE_MANIFEST
    artifact_manifest = artifact_root / "corpus-manifest.json"
    if source_manifest.is_file() and artifact_manifest.is_file():
        if source_manifest.read_bytes() != artifact_manifest.read_bytes():
            errors.append("corpus-manifest.json differs from the source corpus manifest")

    matrix = _candidate_map(documents.get("candidate-matrix.json"), "candidate matrix", errors)
    gates = _candidate_map(documents.get("hard-gates.json"), "hard gates", errors)
    metrics = _candidate_map(documents.get("metrics.json"), "metrics", errors)

    candidate_sets = {
        "candidate matrix": set(matrix),
        "hard gates": set(gates),
        "metrics": set(metrics),
    }
    nonempty_sets = [candidate_ids for candidate_ids in candidate_sets.values() if candidate_ids]
    if nonempty_sets:
        expected_ids = nonempty_sets[0]
        for label, candidate_ids in candidate_sets.items():
            if candidate_ids != expected_ids:
                errors.append(
                    f"{label}: candidate ids differ: expected {sorted(expected_ids)}, "
                    f"found {sorted(candidate_ids)}"
                )

    corpus_digests: set[str] = set()
    for candidate_id in sorted(set(matrix) | set(gates) | set(metrics)):
        matrix_entry = matrix.get(candidate_id, {})
        gate_entry = gates.get(candidate_id, {})
        metric_entry = metrics.get(candidate_id, {})

        gate_items = gate_entry.get("gates")
        if not isinstance(gate_items, list) or not gate_items:
            errors.append(f"{candidate_id}: hard-gate list is absent or empty")
            gate_items = []

        statuses: list[str] = []
        gate_ids: list[str] = []
        for index, gate in enumerate(gate_items):
            if not isinstance(gate, dict):
                errors.append(f"{candidate_id}: gates[{index}] is not an object")
                continue
            gate_id = gate.get("gate_id")
            status = gate.get("status")
            if not isinstance(gate_id, str) or not gate_id:
                errors.append(f"{candidate_id}: gates[{index}] has no gate_id")
            else:
                gate_ids.append(gate_id)
            if status not in _ALLOWED_GATE_STATUSES:
                errors.append(f"{candidate_id}: invalid gate status for {gate_id}: {status!r}")
            else:
                statuses.append(status)
        if len(gate_ids) != len(set(gate_ids)):
            errors.append(f"{candidate_id}: duplicate hard-gate ids")

        pending_ids = sorted(
            gate.get("gate_id")
            for gate in gate_items
            if isinstance(gate, dict) and gate.get("status") == "pending"
        )
        failed_ids = sorted(
            gate.get("gate_id")
            for gate in gate_items
            if isinstance(gate, dict) and gate.get("status") == "failed"
        )
        all_passed = bool(statuses) and all(status == "passed" for status in statuses)

        if gate_entry.get("pending_gate_ids") != pending_ids:
            errors.append(f"{candidate_id}: pending_gate_ids do not match gate statuses")
        if gate_entry.get("passed") is not all_passed:
            errors.append(
                f"{candidate_id}: aggregate passed must be true only when every gate passed"
            )
        if matrix_entry.get("pending_gate_ids") != pending_ids:
            errors.append(f"{candidate_id}: matrix pending_gate_ids drift from hard gates")
        if matrix_entry.get("hard_gates_passed") is not all_passed:
            errors.append(f"{candidate_id}: matrix hard_gates_passed is inconsistent")
        if matrix_entry.get("selection_eligible") is not all_passed:
            errors.append(
                f"{candidate_id}: selection_eligible must be false for pending or failed gates"
            )
        if failed_ids and matrix_entry.get("selection_eligible") is True:
            errors.append(f"{candidate_id}: failed candidate is marked selection eligible")

        config_digest = matrix_entry.get("configuration_digest")
        if not isinstance(config_digest, str) or not _SHA256_RE.fullmatch(config_digest):
            errors.append(f"{candidate_id}: invalid or missing configuration_digest")
        corpus_digest = matrix_entry.get("corpus_digest")
        if not isinstance(corpus_digest, str) or not _SHA256_RE.fullmatch(corpus_digest):
            errors.append(f"{candidate_id}: invalid or missing corpus_digest")
        else:
            corpus_digests.add(corpus_digest)
        metric_corpus_digest = metric_entry.get("corpus_digest")
        if metric_corpus_digest is not None and metric_corpus_digest != corpus_digest:
            errors.append(f"{candidate_id}: metric corpus digest differs from matrix")

        result_path = root / _CANDIDATE_RESULTS_DIR / f"{candidate_id}.json"
        result = _load_json(result_path, f"candidate result {candidate_id}", errors)
        if isinstance(result, dict):
            if result.get("candidate_id") != candidate_id:
                errors.append(f"{candidate_id}: candidate-result identity mismatch")
            if result.get("configuration_digest") != config_digest:
                errors.append(f"{candidate_id}: candidate-result configuration digest mismatch")
            if result.get("corpus_digest") != corpus_digest:
                errors.append(f"{candidate_id}: candidate-result corpus digest mismatch")
            if result.get("hard_gates") != gate_entry:
                errors.append(f"{candidate_id}: aggregate hard gates differ from candidate result")

    if len(corpus_digests) > 1:
        errors.append(f"candidate matrix contains multiple corpus digests: {sorted(corpus_digests)}")

    recommendation_path = artifact_root / "recommendation.md"
    if recommendation_path.is_file():
        recommendation = recommendation_path.read_text(encoding="utf-8")
        for candidate_id in matrix:
            if candidate_id not in recommendation:
                errors.append(f"recommendation does not identify candidate: {candidate_id}")

    artifact_digests = {
        path.relative_to(root).as_posix(): _sha256_file(path)
        for path in required_paths
        if path.is_file()
    }
    receipt = {
        "schema_version": 1,
        "validator": "scripts/validate_redaction_evaluation_hosted.py",
        "head_sha": current_head,
        "expected_head_sha": expected_head.lower() if expected_head else None,
        "status": "failed" if errors else "passed",
        "candidate_ids": sorted(matrix),
        "artifact_sha256": artifact_digests,
        "error_count": len(set(errors)),
    }
    return sorted(set(errors)), receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_ROOT)
    parser.add_argument("--expected-head", default=None)
    parser.add_argument("--receipt", type=Path, default=None)
    args = parser.parse_args(argv)

    errors, receipt = validate_repository(args.root, expected_head=args.expected_head)
    if args.receipt is not None:
        receipt_path = args.receipt
        if not receipt_path.is_absolute():
            receipt_path = args.root / receipt_path
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        print(f"\n{len(errors)} hosted evaluation validation error(s).", file=sys.stderr)
        return 1

    print("OK: committed ADR-0020 evaluation evidence is internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
