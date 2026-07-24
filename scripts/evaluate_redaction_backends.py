# SPDX-License-Identifier: MIT
"""Deterministic top-level orchestrator for the ADR-0020 redaction evaluation.

One command regenerates the whole evidence chain (corpus validation ->
candidate runs -> benchmarks/offline/inventory -> external-verdict merge ->
aggregates -> weighted scores -> evaluation-input digest -> artifact manifest
-> recommendation bindings -> reproducibility check), failing non-zero on
digest drift, malformed annotations, missing artifacts, hand-edited
artifacts, stale recommendation bindings, or non-reproducible aggregates,
per the evaluation contract.

Run from the repository root inside the evaluation venv, e.g.::

    python scripts/evaluate_redaction_backends.py validate-corpus
    python scripts/evaluate_redaction_backends.py evaluate --all
    python scripts/evaluate_redaction_backends.py merge-verdicts
    python scripts/evaluate_redaction_backends.py aggregate
    python scripts/evaluate_redaction_backends.py bind-recommendation
    python scripts/evaluate_redaction_backends.py verify
    python scripts/evaluate_redaction_backends.py review --pr-number N \
        --head-sha <sha> --reviewed-at 2026-07-24T00:00:00Z
    python scripts/evaluate_redaction_backends.py all
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import io
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.redaction_evaluation import review  # noqa: E402
from runtime.redaction_evaluation.backends import CANDIDATE_IDS  # noqa: E402
from runtime.redaction_evaluation.input_digest import (  # noqa: E402
    compute_evaluation_input_digest,
)
from runtime.redaction_evaluation.metrics import (  # noqa: E402
    compute_metrics,
    entity_results_rows,
)
from runtime.redaction_evaluation.policy import RedactionPolicy  # noqa: E402
from runtime.redaction_evaluation.runner import run_candidate  # noqa: E402
from runtime.redaction_evaluation.scoring import (  # noqa: E402
    compute_weighted_scores,
    derive_gate_aggregate,
)

DEFAULT_OUT = REPO_ROOT / "artifacts" / "redaction-evaluation"
MANIFEST_PATH = REPO_ROOT / "tests" / "redaction_evaluation" / "corpus-manifest.json"
SCHEMA_DIR = REPO_ROOT / "tests" / "redaction_evaluation" / "schema"

REQUIRED_ARTIFACTS = (
    "corpus-manifest.json",
    "candidate-matrix.json",
    "hard-gates.json",
    "metrics.json",
    "entity-results.csv",
    "benchmark-results.json",
    "dependency-report.json",
    "license-report.json",
    "vulnerability-report.json",
    "offline-proof.json",
    "memory-isolated.json",
    "weighted-scores.json",
    "evaluation-input.json",
    "artifact-manifest.json",
    "recommendation.md",
)

#: Fixed artifact set bound by artifact-manifest.json (candidate-results/*.json
#: are added dynamically). The manifest deliberately excludes itself, the
#: adversarial review, hosted receipts, and the regenerated draft.
MANIFEST_ARTIFACTS = (
    "benchmark-results.json",
    "candidate-matrix.json",
    "candidate-research-matrix.json",
    "corpus-manifest.json",
    "dependency-report.json",
    "entity-results.csv",
    "environment.json",
    "evaluation-input.json",
    "hard-gates.json",
    "license-report.json",
    "memory-isolated.json",
    "metrics.json",
    "offline-proof.json",
    "recommendation.md",
    "vulnerability-report.json",
    "weighted-scores.json",
)

#: Artifacts whose digests are bound inside the recommendation bindings block.
BINDING_DIGEST_ARTIFACTS = ("metrics.json", "hard-gates.json", "weighted-scores.json")

CSV_HEADER = (
    "candidate_id",
    "dimension",
    "dimension_value",
    "category",
    "tp",
    "fp",
    "fn",
    "precision",
    "recall",
    "f1",
    "f2",
    "exact_span",
    "notes",
)

ENVIRONMENT_PACKAGES = (
    "presidio-analyzer",
    "spacy",
    "en-core-web-lg",
    "gliner",
    "torch",
    "transformers",
    "onnxruntime",
    "datafog",
)


def _fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def _write_text(path: Path, text: str) -> None:
    """Write UTF-8 with LF endings on every platform.

    Artifact digests are byte-exact (artifact-manifest.json, recommendation
    bindings, hosted validation), so newline translation must never make the
    on-disk bytes differ from the regenerated canonical text.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, document: Any) -> None:
    _write_text(path, _dumps(document))


def _dumps(document: Any) -> str:
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _text_sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_manifest() -> dict[str, Any]:
    data: dict[str, Any] = _load_json(MANIFEST_PATH)
    return data


def _corpus_digest(manifest: dict[str, Any]) -> str:
    concatenated = "".join(
        sorted(str(record["input_sha256"]) for record in manifest["records"])
    )
    return "sha256:" + hashlib.sha256(concatenated.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# validate-corpus
# ---------------------------------------------------------------------------


def _corpus_validation_errors() -> list[str]:
    """Validate manifest schema, file digests, and expected annotations."""

    if not MANIFEST_PATH.is_file():
        return [f"corpus manifest missing: {MANIFEST_PATH}"]
    jsonschema = importlib.import_module("jsonschema")

    manifest = _load_manifest()
    manifest_schema = _load_json(SCHEMA_DIR / "corpus-manifest.schema.json")
    expected_schema = _load_json(SCHEMA_DIR / "expected-record.schema.json")
    try:
        jsonschema.validate(manifest, manifest_schema)
    except jsonschema.ValidationError as error:
        return [f"manifest schema violation: {error.message}"]

    errors: list[str] = []
    for record in manifest["records"]:
        record_id = record["record_id"]
        for path_key, digest_key in (
            ("input_path", "input_sha256"),
            ("expected_path", "expected_sha256"),
        ):
            file_path = REPO_ROOT / record[path_key]
            if not file_path.is_file():
                errors.append(f"{record_id}: missing file {record[path_key]}")
                continue
            if _file_sha256(file_path) != record[digest_key]:
                errors.append(f"{record_id}: digest drift on {record[path_key]}")
        expected_file = REPO_ROOT / record["expected_path"]
        if expected_file.is_file():
            try:
                expected_doc = _load_json(expected_file)
                jsonschema.validate(expected_doc, expected_schema)
            except (ValueError, jsonschema.ValidationError) as error:
                errors.append(f"{record_id}: malformed expected record: {error}")
            else:
                if expected_doc.get("record_id") != record_id:
                    errors.append(f"{record_id}: expected record_id mismatch")
    return errors


def cmd_validate_corpus(_args: argparse.Namespace) -> int:
    errors = _corpus_validation_errors()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return _fail(f"corpus validation failed ({len(errors)} problem(s))")
    manifest = _load_manifest()
    print(f"corpus OK: {len(manifest['records'])} records")
    print(f"corpus digest: {_corpus_digest(manifest)}")
    return 0


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------


def _candidate_ids(args: argparse.Namespace) -> list[str]:
    if getattr(args, "all", False):
        return list(CANDIDATE_IDS)
    if getattr(args, "candidate", None):
        return [args.candidate]
    raise SystemExit("specify --candidate <id> or --all")


def cmd_evaluate(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    results_dir = out_dir / "candidate-results"
    metrics_dir = out_dir / "metrics"
    policy = RedactionPolicy()
    failures = 0
    for candidate_id in _candidate_ids(args):
        print(f"evaluating {candidate_id} ...")
        try:
            result = run_candidate(candidate_id, repo_root=REPO_ROOT, policy=policy)
            metrics_doc = compute_metrics(result, repo_root=REPO_ROOT)
        except Exception as error:  # keep the run going; fail at the end
            print(f"ERROR: {candidate_id}: {type(error).__name__}: {error}")
            failures += 1
            continue
        _write_json(results_dir / f"{candidate_id}.json", result)
        _write_json(metrics_dir / f"{candidate_id}.json", metrics_doc)
        gates = result["hard_gates"]
        print(
            f"  outcome: gates_passed={gates['passed']} "
            f"pending={gates['pending_gate_ids']}"
        )
    return 1 if failures else 0


# ---------------------------------------------------------------------------
# merge-verdicts: fold external offline/license verdicts into candidate results
# ---------------------------------------------------------------------------


def _verdict_map(document: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(document, dict):
        return {}
    candidates = document.get("candidates")
    if isinstance(candidates, dict):
        return {
            str(candidate_id): entry
            for candidate_id, entry in candidates.items()
            if isinstance(entry, dict)
        }
    if isinstance(candidates, list):
        return {
            str(entry.get("candidate_id")): entry
            for entry in candidates
            if isinstance(entry, dict)
        }
    return {}


def _external_gate_verdicts(
    out_dir: Path,
) -> tuple[dict[str, bool | None], dict[str, bool | None]]:
    """Per-candidate verdicts from offline-proof.json and license-report.json.

    Offline: the netguard ``passed`` boolean. License:
    ``compatible_with_distribution`` True -> passed, False -> failed, the
    honest ``"review_required"`` non-verdict -> ``None`` (the gate stays
    pending for the owner rather than passing silently).
    """

    def _read(name: str) -> dict[str, dict[str, Any]]:
        path = out_dir / name
        if not path.is_file():
            return {}
        try:
            return _verdict_map(_load_json(path))
        except ValueError:
            return {}

    offline_entries = _read("offline-proof.json")
    license_entries = _read("license-report.json")

    offline: dict[str, bool | None] = {}
    for candidate_id, entry in offline_entries.items():
        passed = entry.get("passed")
        offline[candidate_id] = passed if isinstance(passed, bool) else None

    licenses: dict[str, bool | None] = {}
    for candidate_id, entry in license_entries.items():
        compatible = entry.get("compatible_with_distribution")
        licenses[candidate_id] = (
            compatible if isinstance(compatible, bool) else None
        )
    return offline, licenses


def _merge_candidate_gates(
    hard_gates: dict[str, Any],
    offline_verdict: bool | None,
    license_verdict: bool | None,
) -> dict[str, Any]:
    """Fold external verdicts into one candidate's hard-gate block.

    Pending ``no-undeclared-network`` / ``license-compatible`` gates receive
    the external verdict (a ``None`` verdict leaves the gate pending), then
    ``aggregate_state`` / ``passed`` / ``pending_gate_ids`` /
    ``failed_gate_ids`` are recomputed from the gate statuses. Pure function:
    the input block is not mutated.
    """

    merged: dict[str, Any] = json.loads(json.dumps(hard_gates))
    for gate in merged.get("gates", []):
        if not isinstance(gate, dict) or gate.get("status") != "pending":
            continue
        if gate.get("gate_id") == "no-undeclared-network" and (
            offline_verdict is not None
        ):
            gate["status"] = "passed" if offline_verdict else "failed"
            gate["evidence"] = "artifact:offline-proof.json"
        elif gate.get("gate_id") == "license-compatible" and (
            license_verdict is not None
        ):
            gate["status"] = "passed" if license_verdict else "failed"
            gate["evidence"] = "artifact:license-report.json"
    state, passed, pending, failed = derive_gate_aggregate(merged.get("gates", []))
    merged["aggregate_state"] = state
    merged["passed"] = passed
    merged["pending_gate_ids"] = pending
    merged["failed_gate_ids"] = failed
    return merged


def cmd_merge_verdicts(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    results_dir = out_dir / "candidate-results"
    paths = sorted(results_dir.glob("*.json")) if results_dir.is_dir() else []
    if not paths:
        return _fail("no candidate results found; run `evaluate` first")
    offline, licenses = _external_gate_verdicts(out_dir)
    changed: list[str] = []
    for path in paths:
        document = _load_json(path)
        candidate_id = str(document.get("candidate_id"))
        merged = _merge_candidate_gates(
            document.get("hard_gates") or {},
            offline.get(candidate_id),
            licenses.get(candidate_id),
        )
        if merged != document.get("hard_gates"):
            document["hard_gates"] = merged
            _write_json(path, document)
            changed.append(candidate_id)
    print(
        "merge-verdicts: updated "
        + (", ".join(changed) if changed else "nothing (already merged)")
    )
    return 0


def _merge_idempotency_errors(out_dir: Path) -> list[str]:
    """Committed candidate results must already reflect the external verdicts."""

    results_dir = out_dir / "candidate-results"
    paths = sorted(results_dir.glob("*.json")) if results_dir.is_dir() else []
    offline, licenses = _external_gate_verdicts(out_dir)
    errors: list[str] = []
    for path in paths:
        document = _load_json(path)
        candidate_id = str(document.get("candidate_id"))
        merged = _merge_candidate_gates(
            document.get("hard_gates") or {},
            offline.get(candidate_id),
            licenses.get(candidate_id),
        )
        if merged != document.get("hard_gates"):
            errors.append(
                f"{candidate_id}: candidate-result hard_gates do not reflect the "
                "external gate verdicts and derived aggregate state; run "
                "merge-verdicts"
            )
    return errors


# ---------------------------------------------------------------------------
# aggregate (+ weighted scores, evaluation-input digest, artifact manifest)
# ---------------------------------------------------------------------------


def _load_candidate_results(out_dir: Path) -> list[dict[str, Any]]:
    results_dir = out_dir / "candidate-results"
    documents: list[dict[str, Any]] = []
    if results_dir.is_dir():
        for path in sorted(results_dir.glob("*.json")):
            documents.append(_load_json(path))
    return documents


def _regenerate_documents(out_dir: Path) -> dict[str, str]:
    """Regenerate every derivable artifact as exact canonical text.

    Returns filename -> text for metrics.json, entity-results.csv,
    hard-gates.json, candidate-matrix.json, weighted-scores.json, and
    evaluation-input.json, all computed from the committed candidate results,
    corpus, benchmark/memory artifacts, and evaluator code. Raises
    ``RuntimeError`` with a precise message when a required input is missing.
    """

    results = _load_candidate_results(out_dir)
    if not results:
        raise RuntimeError("no candidate results found; run `evaluate` first")

    input_document = compute_evaluation_input_digest(REPO_ROOT)
    evaluation_input_sha256 = str(input_document["evaluation_input_sha256"])

    metrics_docs = [compute_metrics(result, repo_root=REPO_ROOT) for result in results]
    metrics_json = {
        "schema_version": 1,
        "corpus_digest": results[0].get("corpus_digest"),
        "evaluation_input_sha256": evaluation_input_sha256,
        "candidates": sorted(metrics_docs, key=lambda d: str(d["candidate_id"])),
    }
    hard_gates_json = {
        "schema_version": 1,
        "evaluation_input_sha256": evaluation_input_sha256,
        # Copied VERBATIM from each candidate result: hosted validation
        # asserts dict equality between the aggregate entry and the
        # candidate-result hard_gates block.
        "candidates": sorted(
            (result["hard_gates"] for result in results),
            key=lambda g: str(g["candidate_id"]),
        ),
    }

    matrix_candidates: list[dict[str, Any]] = []
    for result in sorted(results, key=lambda r: str(r["candidate_id"])):
        gates = result["hard_gates"].get("gates", [])
        state, all_passed, pending, _failed = derive_gate_aggregate(
            gates if isinstance(gates, list) else []
        )
        matrix_candidates.append(
            {
                "candidate_id": result["candidate_id"],
                "family": result["identity"]["family"],
                "engine_version": result["identity"]["engine_version"],
                "packages": result["identity"]["packages"],
                "models": result["identity"]["models"],
                "configuration_digest": result["configuration_digest"],
                "corpus_digest": result["corpus_digest"],
                "aggregate_state": state,
                "hard_gates_passed": all_passed,
                "pending_gate_ids": pending,
                "selection_eligible": all_passed,
            }
        )
    matrix = {
        "schema_version": 1,
        "evaluation_input_sha256": evaluation_input_sha256,
        "candidates": matrix_candidates,
    }

    for name in ("benchmark-results.json", "memory-isolated.json"):
        if not (out_dir / name).is_file():
            raise RuntimeError(
                f"{name} is required for weighted scoring and is missing; "
                "run the benchmark/memory steps first"
            )
    weighted = compute_weighted_scores(
        metrics_json,
        hard_gates_json,
        _load_json(out_dir / "benchmark-results.json"),
        _load_json(out_dir / "memory-isolated.json"),
    )
    weighted["evaluation_input_sha256"] = evaluation_input_sha256

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_HEADER, lineterminator="\n")
    writer.writeheader()
    for row in entity_results_rows(metrics_docs):
        writer.writerow(
            {key: ("" if row[key] is None else row[key]) for key in CSV_HEADER}
        )

    return {
        "metrics.json": _dumps(metrics_json),
        "entity-results.csv": buffer.getvalue(),
        "hard-gates.json": _dumps(hard_gates_json),
        "candidate-matrix.json": _dumps(matrix),
        "weighted-scores.json": _dumps(weighted),
        "evaluation-input.json": _dumps(input_document),
    }


def _artifact_manifest_document(out_dir: Path) -> dict[str, Any]:
    """Digest every bound artifact file (fixed list + candidate results)."""

    artifacts: dict[str, str] = {}
    missing: list[str] = []
    for name in MANIFEST_ARTIFACTS:
        path = out_dir / name
        if path.is_file():
            artifacts[name] = _file_sha256(path)
        else:
            missing.append(name)
    results_dir = out_dir / "candidate-results"
    result_paths = sorted(results_dir.glob("*.json")) if results_dir.is_dir() else []
    if not result_paths:
        missing.append("candidate-results/*.json")
    for path in result_paths:
        artifacts[f"candidate-results/{path.name}"] = _file_sha256(path)
    if missing:
        raise RuntimeError(
            "cannot build artifact-manifest.json; missing artifact(s): "
            + ", ".join(missing)
        )
    return {"schema_version": 1, "artifacts": artifacts}


def _manifest_drift_errors(out_dir: Path) -> list[str]:
    """Recompute artifact digests and diff them against the committed manifest."""

    try:
        expected = _artifact_manifest_document(out_dir)
    except RuntimeError as error:
        return [str(error)]
    manifest_path = out_dir / "artifact-manifest.json"
    if not manifest_path.is_file():
        return ["artifact-manifest.json is missing; run `aggregate`"]
    if manifest_path.read_bytes() == _dumps(expected).encode("utf-8"):
        return []
    try:
        committed = _load_json(manifest_path)
    except ValueError:
        return ["artifact-manifest.json is not valid JSON"]
    committed_artifacts = (
        committed.get("artifacts", {}) if isinstance(committed, dict) else {}
    )
    errors: list[str] = []
    for name in sorted(set(expected["artifacts"]) | set(committed_artifacts)):
        expected_digest = expected["artifacts"].get(name)
        committed_digest = committed_artifacts.get(name)
        if expected_digest != committed_digest:
            errors.append(
                f"artifact-manifest.json drift for {name}: the committed digest "
                "does not match the file on disk (hand-edited artifact?)"
            )
    return errors or [
        "artifact-manifest.json does not reproduce (structural drift)"
    ]


def _recommendation_draft(matrix: dict[str, Any]) -> str:
    lines = [
        "# Redaction backend evaluation: recommendation draft",
        "",
        "Auto-generated comparative draft (ADR-0020 spike). Advisory only:",
        "the final decision must explain why the measured benefit does or",
        "does not justify migration. This draft grants no selection,",
        "release, or deployment authority.",
        "",
        "| candidate | gate state | pending gates | eligible |",
        "|---|---|---|---|",
    ]
    for candidate in matrix["candidates"]:
        pending = ", ".join(candidate["pending_gate_ids"]) or "-"
        lines.append(
            f"| {candidate['candidate_id']} | "
            f"{candidate['aggregate_state']} | "
            f"{pending} | {'yes' if candidate['selection_eligible'] else 'no'} |"
        )
    lines += [
        "",
        "Quality, preservation, and security metrics: see `metrics.json` and",
        "`entity-results.csv`. Weighted advisory scores: `weighted-scores.json`.",
        "Performance: `benchmark-results.json`, `memory-isolated.json`.",
        "Offline proof: `offline-proof.json`. Licensing/dependencies:",
        "`license-report.json`, `dependency-report.json`,",
        "`vulnerability-report.json`. Input binding: `evaluation-input.json`;",
        "artifact binding: `artifact-manifest.json`.",
        "",
    ]
    return "\n".join(lines)


def cmd_aggregate(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    try:
        regenerated = _regenerate_documents(out_dir)
    except (RuntimeError, FileNotFoundError) as error:
        return _fail(str(error))
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(MANIFEST_PATH, out_dir / "corpus-manifest.json")
    for name, text in regenerated.items():
        _write_text(out_dir / name, text)
    matrix = json.loads(regenerated["candidate-matrix.json"])
    # The auto-draft never overwrites the authored recommendation: the final
    # recommendation is owner-facing judgment layered on these aggregates,
    # while the draft is regenerated evidence.
    _write_text(out_dir / "recommendation-draft.md", _recommendation_draft(matrix))
    try:
        manifest_document = _artifact_manifest_document(out_dir)
    except RuntimeError as error:
        return _fail(str(error))
    _write_json(out_dir / "artifact-manifest.json", manifest_document)
    print(f"aggregates written to {out_dir}")
    return 0


# ---------------------------------------------------------------------------
# recommendation machine bindings
# ---------------------------------------------------------------------------


def _bindings_document(
    matrix: dict[str, Any],
    metrics: dict[str, Any],
    weighted: dict[str, Any],
    evaluation_input_sha256: str,
    artifact_digests: dict[str, str],
) -> dict[str, Any]:
    """Assemble the machine-bindings payload from aggregate documents."""

    metric_map = {
        str(entry.get("candidate_id")): entry
        for entry in metrics.get("candidates", [])
    }
    weighted_map = {
        str(entry.get("candidate_id")): entry
        for entry in weighted.get("candidates", [])
    }
    candidates: list[dict[str, Any]] = []
    for entry in sorted(
        matrix.get("candidates", []), key=lambda c: str(c.get("candidate_id"))
    ):
        candidate_id = str(entry.get("candidate_id"))
        totals = metric_map.get(candidate_id, {}).get("totals", {})
        candidates.append(
            {
                "candidate_id": candidate_id,
                "configuration_digest": entry.get("configuration_digest"),
                "aggregate_state": entry.get("aggregate_state"),
                "selection_eligible": entry.get("selection_eligible"),
                "f2": totals.get("f2"),
                "recall": totals.get("recall"),
                "precision": totals.get("precision"),
                "weighted_total": weighted_map.get(candidate_id, {}).get("total"),
            }
        )
    matrix_candidates = matrix.get("candidates", [])
    corpus_sha256 = (
        matrix_candidates[0].get("corpus_digest") if matrix_candidates else None
    )
    return {
        "evaluation_input_sha256": evaluation_input_sha256,
        "corpus_sha256": corpus_sha256,
        "candidates": candidates,
        "artifact_sha256": dict(artifact_digests),
    }


def _expected_bindings(regenerated: dict[str, str]) -> dict[str, Any]:
    """Bindings derived from the freshly regenerated (ground-truth) texts."""

    matrix = json.loads(regenerated["candidate-matrix.json"])
    metrics = json.loads(regenerated["metrics.json"])
    weighted = json.loads(regenerated["weighted-scores.json"])
    input_document = json.loads(regenerated["evaluation-input.json"])
    digests = {
        name: _text_sha256(regenerated[name]) for name in BINDING_DIGEST_ARTIFACTS
    }
    return _bindings_document(
        matrix,
        metrics,
        weighted,
        str(input_document["evaluation_input_sha256"]),
        digests,
    )


def _recommendation_binding_errors(
    out_dir: Path, regenerated: dict[str, str]
) -> list[str]:
    recommendation_path = out_dir / "recommendation.md"
    if not recommendation_path.is_file():
        return ["recommendation.md is missing"]
    text = recommendation_path.read_text(encoding="utf-8")
    errors = review.verify_recommendation_bindings(text, _expected_bindings(regenerated))
    # Every candidate must also be identified in the prose, not only inside
    # the machine block.
    prose = review.strip_bindings_block(text)
    matrix = json.loads(regenerated["candidate-matrix.json"])
    for entry in matrix.get("candidates", []):
        candidate_id = str(entry.get("candidate_id"))
        if candidate_id not in prose:
            errors.append(
                f"recommendation prose does not identify candidate: {candidate_id}"
            )
    return errors


def cmd_bind_recommendation(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    recommendation_path = out_dir / "recommendation.md"
    if not recommendation_path.is_file():
        return _fail("recommendation.md is missing; nothing to bind")
    required = (
        "candidate-matrix.json",
        "metrics.json",
        "weighted-scores.json",
        "evaluation-input.json",
        *BINDING_DIGEST_ARTIFACTS,
    )
    missing = sorted({name for name in required if not (out_dir / name).is_file()})
    if missing:
        return _fail(
            "bind-recommendation requires aggregated artifacts; missing: "
            + ", ".join(missing)
        )
    input_document = _load_json(out_dir / "evaluation-input.json")
    bindings = _bindings_document(
        _load_json(out_dir / "candidate-matrix.json"),
        _load_json(out_dir / "metrics.json"),
        _load_json(out_dir / "weighted-scores.json"),
        str(input_document["evaluation_input_sha256"]),
        {name: _file_sha256(out_dir / name) for name in BINDING_DIGEST_ARTIFACTS},
    )
    text = recommendation_path.read_text(encoding="utf-8")
    updated = review.replace_bindings_block(text, bindings)
    if updated != text:
        _write_text(recommendation_path, updated)
        # recommendation.md participates in the artifact manifest; refresh it
        # so the mechanical block rewrite never reads as a hand-edit.
        try:
            _write_json(
                out_dir / "artifact-manifest.json",
                _artifact_manifest_document(out_dir),
            )
        except RuntimeError as error:
            return _fail(str(error))
        print("recommendation bindings rewritten (manifest refreshed)")
    else:
        print("recommendation bindings already current")
    return 0


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


def _verification_errors(out_dir: Path) -> list[str]:
    """Full reproducibility verification; returns every problem found."""

    errors = list(_corpus_validation_errors())

    missing = [name for name in REQUIRED_ARTIFACTS if not (out_dir / name).is_file()]
    if missing:
        errors.append(f"missing required artifact(s): {', '.join(missing)}")

    artifact_manifest_copy = out_dir / "corpus-manifest.json"
    if artifact_manifest_copy.is_file() and MANIFEST_PATH.is_file():
        if artifact_manifest_copy.read_bytes() != MANIFEST_PATH.read_bytes():
            errors.append(
                "artifact corpus-manifest.json drifted from the source corpus"
            )

    try:
        regenerated = _regenerate_documents(out_dir)
    except (RuntimeError, FileNotFoundError) as error:
        errors.append(str(error))
        return errors

    errors.extend(_merge_idempotency_errors(out_dir))
    for name, expected in regenerated.items():
        path = out_dir / name
        if not path.is_file():
            errors.append(f"{name} is missing; run `aggregate`")
        elif path.read_bytes() != expected.encode("utf-8"):
            errors.append(
                f"{name} does not reproduce byte-for-byte from committed inputs"
            )
    errors.extend(_manifest_drift_errors(out_dir))
    errors.extend(_recommendation_binding_errors(out_dir, regenerated))
    return errors


def cmd_verify(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    errors = _verification_errors(out_dir)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return _fail(f"verification failed ({len(errors)} problem(s))")
    print(
        "verify OK: corpus, aggregates, weighted scores, evaluation-input "
        "digest, artifact manifest, and recommendation bindings all reproduce"
    )
    return 0


# ---------------------------------------------------------------------------
# review
# ---------------------------------------------------------------------------


def cmd_review(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    corpus_errors = _corpus_validation_errors()
    try:
        regenerated = _regenerate_documents(out_dir)
    except (RuntimeError, FileNotFoundError) as error:
        print(f"WARNING: regeneration unavailable: {error}", file=sys.stderr)
        regenerated = {}
    regenerated_with_manifest = dict(regenerated)
    if regenerated:
        try:
            regenerated_with_manifest["artifact-manifest.json"] = _dumps(
                _artifact_manifest_document(out_dir)
            )
        except RuntimeError as error:
            print(f"WARNING: manifest recompute unavailable: {error}", file=sys.stderr)
        binding_errors = _recommendation_binding_errors(out_dir, regenerated)
        merge_errors = _merge_idempotency_errors(out_dir)
    else:
        binding_errors = ["aggregates could not be regenerated"]
        merge_errors = ["aggregates could not be regenerated"]

    checks = review.run_review_checks(
        out_dir,
        corpus_errors=corpus_errors,
        regenerated=regenerated_with_manifest,
        binding_errors=binding_errors,
        merge_errors=merge_errors,
    )
    try:
        document = review.build_adversarial_review(
            out_dir,
            pr_number=args.pr_number,
            head_sha=args.head_sha,
            base_ref=args.base_ref,
            reviewed_at=args.reviewed_at,
            checks=checks,
        )
    except ValueError as error:
        return _fail(str(error))
    _write_json(out_dir / "adversarial-review.json", document)
    print(
        f"adversarial review written: verdict={document['verdict']} "
        f"checks={len(document['checks'])} "
        f"discrepancies={len(document['unresolved_discrepancies'])}"
    )
    return 0


# ---------------------------------------------------------------------------
# all
# ---------------------------------------------------------------------------


def _optional_module(name: str) -> Any | None:
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def _write_environment(out_dir: Path) -> None:
    from importlib import metadata

    versions: dict[str, str | None] = {}
    for package in ENVIRONMENT_PACKAGES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    _write_json(
        out_dir / "environment.json",
        {
            "python_version": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "packages": versions,
            "policy": RedactionPolicy().manifest(),
        },
    )


def cmd_all(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    steps: list[tuple[str, Callable[[], int]]] = [
        ("validate-corpus", lambda: cmd_validate_corpus(args)),
        ("evaluate", lambda: cmd_evaluate(_with_all(args))),
    ]
    for name, step in steps:
        print(f"== {name} ==")
        status = step()
        if status != 0:
            return _fail(f"step failed: {name}")

    policy = RedactionPolicy()
    candidate_ids = list(CANDIDATE_IDS)

    if not args.skip_bench:
        bench = _optional_module("runtime.redaction_evaluation.bench")
        if bench is None:
            print("bench module not importable; skipping benchmark-results.json")
        else:
            benchmarks = {
                candidate_id: bench.run_benchmarks(
                    candidate_id, repo_root=REPO_ROOT, policy=policy
                )
                for candidate_id in candidate_ids
            }
            _write_json(
                out_dir / "benchmark-results.json",
                {"schema_version": 1, "candidates": benchmarks},
            )

    if not args.skip_offline:
        netguard = _optional_module("runtime.redaction_evaluation.netguard")
        if netguard is None:
            print("netguard module not importable; skipping offline-proof.json")
        else:
            _write_json(
                out_dir / "offline-proof.json",
                netguard.offline_proof(
                    candidate_ids, repo_root=REPO_ROOT, policy=policy
                ),
            )

    if not args.skip_inventory:
        inventory = _optional_module("runtime.redaction_evaluation.inventory")
        if inventory is None:
            print("inventory module not importable; skipping inventory artifacts")
        else:
            dependency_report, license_report, vulnerability_report = (
                inventory.build_inventory(candidate_ids)
            )
            _write_json(out_dir / "dependency-report.json", dependency_report)
            _write_json(out_dir / "license-report.json", license_report)
            _write_json(out_dir / "vulnerability-report.json", vulnerability_report)

    _write_environment(out_dir)

    tail_steps: list[tuple[str, Callable[[], int]]] = [
        ("merge-verdicts", lambda: cmd_merge_verdicts(args)),
        ("aggregate", lambda: cmd_aggregate(args)),
        ("bind-recommendation", lambda: cmd_bind_recommendation(args)),
        ("verify", lambda: cmd_verify(args)),
    ]
    for name, step in tail_steps:
        print(f"== {name} ==")
        status = step()
        if status != 0:
            return _fail(f"step failed: {name}")
    return 0


def _with_all(args: argparse.Namespace) -> argparse.Namespace:
    clone = argparse.Namespace(**vars(args))
    clone.all = True
    clone.candidate = None
    return clone


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evaluate_redaction_backends",
        description="Deterministic ADR-0020 redaction evaluation orchestrator",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _add_out(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--out", default=str(DEFAULT_OUT), help="artifact directory")

    sub_validate = subparsers.add_parser(
        "validate-corpus", help="validate manifest, digests, and expected records"
    )
    _add_out(sub_validate)
    sub_validate.set_defaults(func=cmd_validate_corpus)

    sub_evaluate = subparsers.add_parser(
        "evaluate", help="run one candidate (or all) and compute metrics"
    )
    sub_evaluate.add_argument("--candidate", help="candidate id")
    sub_evaluate.add_argument("--all", action="store_true", help="all candidates")
    _add_out(sub_evaluate)
    sub_evaluate.set_defaults(func=cmd_evaluate)

    sub_merge = subparsers.add_parser(
        "merge-verdicts",
        help="fold offline-proof/license verdicts into candidate results",
    )
    _add_out(sub_merge)
    sub_merge.set_defaults(func=cmd_merge_verdicts)

    sub_aggregate = subparsers.add_parser(
        "aggregate",
        help=(
            "write metrics, hard gates, matrix, csv, weighted scores, "
            "evaluation-input digest, and the artifact manifest"
        ),
    )
    _add_out(sub_aggregate)
    sub_aggregate.set_defaults(func=cmd_aggregate)

    sub_bind = subparsers.add_parser(
        "bind-recommendation",
        help=(
            "mechanically (re)write only the fenced machine-bindings block in "
            "recommendation.md from the current artifacts"
        ),
    )
    _add_out(sub_bind)
    sub_bind.set_defaults(func=cmd_bind_recommendation)

    sub_verify = subparsers.add_parser(
        "verify",
        help=(
            "re-validate corpus and reproduce aggregates, weighted scores, "
            "input digest, artifact manifest, and recommendation bindings "
            "byte-for-byte"
        ),
    )
    _add_out(sub_verify)
    sub_verify.set_defaults(func=cmd_verify)

    sub_review = subparsers.add_parser(
        "review",
        help="emit the exact-head adversarial-review artifact",
    )
    sub_review.add_argument("--pr-number", type=int, required=True)
    sub_review.add_argument("--head-sha", required=True)
    sub_review.add_argument("--base-ref", default="main")
    sub_review.add_argument(
        "--reviewed-at",
        required=True,
        help="explicit UTC timestamp (e.g. 2026-07-24T00:00:00Z); no implicit now()",
    )
    _add_out(sub_review)
    sub_review.set_defaults(func=cmd_review)

    sub_all = subparsers.add_parser(
        "all",
        help=(
            "validate -> evaluate --all -> bench -> offline -> inventory -> "
            "merge-verdicts -> aggregate -> bind-recommendation -> verify"
        ),
    )
    _add_out(sub_all)
    sub_all.add_argument("--skip-bench", action="store_true")
    sub_all.add_argument("--skip-offline", action="store_true")
    sub_all.add_argument("--skip-inventory", action="store_true")
    sub_all.set_defaults(func=cmd_all)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.func
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
