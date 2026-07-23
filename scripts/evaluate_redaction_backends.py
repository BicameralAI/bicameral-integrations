# SPDX-License-Identifier: MIT
"""Deterministic top-level orchestrator for the ADR-0020 redaction evaluation.

One command regenerates the whole evidence chain (corpus validation ->
candidate runs -> aggregate metrics -> hard gates -> reproducibility check),
failing non-zero on digest drift, malformed annotations, missing artifacts, or
non-reproducible aggregates, per the evaluation contract.

Run from the repository root inside the evaluation venv, e.g.::

    python scripts/evaluate_redaction_backends.py validate-corpus
    python scripts/evaluate_redaction_backends.py evaluate --all
    python scripts/evaluate_redaction_backends.py aggregate
    python scripts/evaluate_redaction_backends.py verify
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

from runtime.redaction_evaluation.backends import CANDIDATE_IDS  # noqa: E402
from runtime.redaction_evaluation.metrics import (  # noqa: E402
    compute_metrics,
    entity_results_rows,
)
from runtime.redaction_evaluation.policy import RedactionPolicy  # noqa: E402
from runtime.redaction_evaluation.runner import run_candidate  # noqa: E402

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
    "recommendation.md",
)

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


def _write_json(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _dumps(document: Any) -> str:
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_manifest() -> dict[str, Any]:
    with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        data: dict[str, Any] = json.load(handle)
    return data


def _corpus_digest(manifest: dict[str, Any]) -> str:
    concatenated = "".join(
        sorted(str(record["input_sha256"]) for record in manifest["records"])
    )
    return "sha256:" + hashlib.sha256(concatenated.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# validate-corpus
# ---------------------------------------------------------------------------


def cmd_validate_corpus(_args: argparse.Namespace) -> int:
    if not MANIFEST_PATH.is_file():
        return _fail(f"corpus manifest missing: {MANIFEST_PATH}")
    jsonschema = importlib.import_module("jsonschema")

    manifest = _load_manifest()
    manifest_schema = json.loads(
        (SCHEMA_DIR / "corpus-manifest.schema.json").read_text(encoding="utf-8")
    )
    expected_schema = json.loads(
        (SCHEMA_DIR / "expected-record.schema.json").read_text(encoding="utf-8")
    )
    try:
        jsonschema.validate(manifest, manifest_schema)
    except jsonschema.ValidationError as error:
        return _fail(f"manifest schema violation: {error.message}")

    failures = 0
    for record in manifest["records"]:
        record_id = record["record_id"]
        for path_key, digest_key in (
            ("input_path", "input_sha256"),
            ("expected_path", "expected_sha256"),
        ):
            file_path = REPO_ROOT / record[path_key]
            if not file_path.is_file():
                print(f"ERROR: {record_id}: missing file {record[path_key]}")
                failures += 1
                continue
            actual = _file_sha256(file_path)
            if actual != record[digest_key]:
                print(f"ERROR: {record_id}: digest drift on {record[path_key]}")
                failures += 1
        expected_file = REPO_ROOT / record["expected_path"]
        if expected_file.is_file():
            try:
                expected_doc = json.loads(expected_file.read_text(encoding="utf-8"))
                jsonschema.validate(expected_doc, expected_schema)
            except (ValueError, jsonschema.ValidationError) as error:
                print(f"ERROR: {record_id}: malformed expected record: {error}")
                failures += 1
            else:
                if expected_doc.get("record_id") != record_id:
                    print(f"ERROR: {record_id}: expected record_id mismatch")
                    failures += 1
    if failures:
        return _fail(f"corpus validation failed ({failures} problem(s))")
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
# aggregate
# ---------------------------------------------------------------------------


def _load_candidate_results(out_dir: Path) -> list[dict[str, Any]]:
    results_dir = out_dir / "candidate-results"
    documents: list[dict[str, Any]] = []
    if results_dir.is_dir():
        for path in sorted(results_dir.glob("*.json")):
            documents.append(json.loads(path.read_text(encoding="utf-8")))
    return documents


def _aggregate_documents(
    out_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    """Recompute (metrics.json, hard-gates.json, candidate-matrix.json, csv)."""

    results = _load_candidate_results(out_dir)
    if not results:
        raise RuntimeError("no candidate results found; run `evaluate` first")
    metrics_docs = [
        compute_metrics(result, repo_root=REPO_ROOT) for result in results
    ]
    metrics_json = {
        "schema_version": 1,
        "corpus_digest": results[0].get("corpus_digest"),
        "candidates": sorted(metrics_docs, key=lambda d: str(d["candidate_id"])),
    }
    hard_gates_json = {
        "schema_version": 1,
        "candidates": sorted(
            (result["hard_gates"] for result in results),
            key=lambda g: str(g["candidate_id"]),
        ),
    }
    matrix = {
        "schema_version": 1,
        "candidates": [
            {
                "candidate_id": result["candidate_id"],
                "family": result["identity"]["family"],
                "engine_version": result["identity"]["engine_version"],
                "packages": result["identity"]["packages"],
                "models": result["identity"]["models"],
                "configuration_digest": result["configuration_digest"],
                "corpus_digest": result["corpus_digest"],
                "hard_gates_passed": result["hard_gates"]["passed"],
                "pending_gate_ids": result["hard_gates"]["pending_gate_ids"],
                "selection_eligible": result["hard_gates"]["passed"],
            }
            for result in sorted(results, key=lambda r: str(r["candidate_id"]))
        ],
    }
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_HEADER, lineterminator="\n")
    writer.writeheader()
    for row in entity_results_rows(metrics_docs):
        writer.writerow(
            {key: ("" if row[key] is None else row[key]) for key in CSV_HEADER}
        )
    return metrics_json, hard_gates_json, matrix, buffer.getvalue()


def _recommendation_draft(matrix: dict[str, Any]) -> str:
    lines = [
        "# Redaction backend evaluation: recommendation draft",
        "",
        "Auto-generated comparative draft (ADR-0020 spike). Advisory only:",
        "the final decision must explain why the measured benefit does or",
        "does not justify migration. This draft grants no selection,",
        "release, or deployment authority.",
        "",
        "| candidate | hard gates | pending gates | eligible |",
        "|---|---|---|---|",
    ]
    for candidate in matrix["candidates"]:
        pending = ", ".join(candidate["pending_gate_ids"]) or "-"
        lines.append(
            f"| {candidate['candidate_id']} | "
            f"{'passed' if candidate['hard_gates_passed'] else 'FAILED'} | "
            f"{pending} | {'yes' if candidate['selection_eligible'] else 'no'} |"
        )
    lines += [
        "",
        "Quality, preservation, and security metrics: see `metrics.json` and",
        "`entity-results.csv`. Performance: `benchmark-results.json`.",
        "Offline proof: `offline-proof.json`. Licensing/dependencies:",
        "`license-report.json`, `dependency-report.json`,",
        "`vulnerability-report.json`.",
        "",
    ]
    return "\n".join(lines)


def cmd_aggregate(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    try:
        metrics_json, hard_gates_json, matrix, csv_text = _aggregate_documents(out_dir)
    except RuntimeError as error:
        return _fail(str(error))
    _write_json(out_dir / "metrics.json", metrics_json)
    _write_json(out_dir / "hard-gates.json", hard_gates_json)
    _write_json(out_dir / "candidate-matrix.json", matrix)
    (out_dir / "entity-results.csv").write_text(csv_text, encoding="utf-8")
    # The auto-draft never overwrites the authored recommendation: the final
    # recommendation is owner-facing judgment layered on these aggregates,
    # while the draft is regenerated evidence.
    (out_dir / "recommendation-draft.md").write_text(
        _recommendation_draft(matrix), encoding="utf-8"
    )
    print(f"aggregates written to {out_dir}")
    return 0


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


def cmd_verify(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    status = cmd_validate_corpus(args)
    if status != 0:
        return status
    missing = [
        name for name in REQUIRED_ARTIFACTS if not (out_dir / name).is_file()
    ]
    if missing:
        return _fail(f"missing required artifact(s): {', '.join(missing)}")
    try:
        metrics_json, _hard_gates_json, _matrix, csv_text = _aggregate_documents(
            out_dir
        )
    except RuntimeError as error:
        return _fail(str(error))
    written_metrics = (out_dir / "metrics.json").read_text(encoding="utf-8")
    if written_metrics != _dumps(metrics_json):
        return _fail("metrics.json does not reproduce from candidate-results")
    written_csv = (out_dir / "entity-results.csv").read_text(encoding="utf-8")
    if written_csv != csv_text:
        return _fail("entity-results.csv does not reproduce from candidate-results")
    manifest_copy = json.loads(
        (out_dir / "corpus-manifest.json").read_text(encoding="utf-8")
    )
    if _corpus_digest(manifest_copy) != _corpus_digest(_load_manifest()):
        return _fail("artifact corpus-manifest.json drifted from the source corpus")
    print("verify OK: aggregates reproduce and all required artifacts exist")
    return 0


# ---------------------------------------------------------------------------
# all
# ---------------------------------------------------------------------------


def _optional_module(name: str) -> Any | None:
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def _merge_external_gate_verdicts(out_dir: Path) -> None:
    """Fill pending no-undeclared-network / license-compatible gates from the
    externally produced artifacts, when their shape is recognizable."""

    gates_path = out_dir / "hard-gates.json"
    if not gates_path.is_file():
        return
    hard_gates = json.loads(gates_path.read_text(encoding="utf-8"))

    def _per_candidate_verdicts(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return {}
        candidates = document.get("candidates")
        if isinstance(candidates, dict):
            return candidates
        if isinstance(candidates, list):
            return {
                str(entry.get("candidate_id")): entry
                for entry in candidates
                if isinstance(entry, dict)
            }
        return {}

    offline = _per_candidate_verdicts(out_dir / "offline-proof.json")
    licenses = _per_candidate_verdicts(out_dir / "license-report.json")

    def _verdict(entry: Any) -> bool | None:
        if not isinstance(entry, dict):
            return None
        for key in ("passed", "compatible", "ok"):
            if isinstance(entry.get(key), bool):
                verdict: bool = entry[key]
                return verdict
        attempts = entry.get("undeclared_attempts")
        if isinstance(attempts, int):
            return attempts == 0
        return None

    changed = False
    for candidate in hard_gates.get("candidates", []):
        candidate_id = str(candidate.get("candidate_id"))
        for gate in candidate.get("gates", []):
            if gate.get("status") != "pending":
                continue
            source = None
            evidence = None
            if gate.get("gate_id") == "no-undeclared-network":
                source = _verdict(offline.get(candidate_id))
                evidence = "artifact:offline-proof.json"
            elif gate.get("gate_id") == "license-compatible":
                source = _verdict(licenses.get(candidate_id))
                evidence = "artifact:license-report.json"
            if source is not None:
                gate["status"] = "passed" if source else "failed"
                gate["evidence"] = evidence
                changed = True
        candidate["pending_gate_ids"] = [
            g["gate_id"] for g in candidate.get("gates", []) if g["status"] == "pending"
        ]
        candidate["passed"] = not any(
            g["status"] == "failed" for g in candidate.get("gates", [])
        )
    if changed:
        _write_json(gates_path, hard_gates)


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
        ("aggregate", lambda: cmd_aggregate(args)),
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

    _merge_external_gate_verdicts(out_dir)
    _write_environment(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(MANIFEST_PATH, out_dir / "corpus-manifest.json")

    print("== verify ==")
    return cmd_verify(args)


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

    sub_aggregate = subparsers.add_parser(
        "aggregate", help="write metrics.json, hard-gates.json, entity-results.csv"
    )
    _add_out(sub_aggregate)
    sub_aggregate.set_defaults(func=cmd_aggregate)

    sub_verify = subparsers.add_parser(
        "verify", help="re-validate corpus and reproduce aggregates byte-for-byte"
    )
    _add_out(sub_verify)
    sub_verify.set_defaults(func=cmd_verify)

    sub_all = subparsers.add_parser(
        "all", help="validate -> evaluate --all -> aggregate -> extras -> verify"
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
