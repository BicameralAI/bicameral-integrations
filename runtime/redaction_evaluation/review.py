# SPDX-License-Identifier: MIT
"""Adversarial-review generation and recommendation machine bindings.

Two responsibilities, both artifact-side and model-free:

1. The ``recommendation.md`` machine-bindings block: a fenced
   ```` ```json redaction-recommendation-bindings ```` block that binds the
   prose recommendation to the regenerable evidence (evaluation-input digest,
   corpus digest, per-candidate gate state and headline metrics, and the
   digests of the score-bearing artifacts). Parsing, rendering, in-place
   replacement, and drift verification live here.

2. The exact-head adversarial-review artifact
   (``artifacts/redaction-evaluation/adversarial-review.json``): every check
   is derived from actually executed verification (the orchestrator passes in
   the regenerated documents and error lists), discrepancies are derived (a
   pending hard gate yields a high-severity owner-decision item, a failed
   check yields a blocker), and the emitted document is validated against
   ``tests/redaction_evaluation/schema/adversarial-review.schema.json``
   before it is ever written.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .scoring import derive_gate_aggregate

REPOSITORY = "BicameralAI/bicameral-integrations"
PARENT_BASELINE_PR = 269
PARENT_BASELINE_HEAD = "fd69ff2742363b5d619bc073b8e8490c0f50733d"

BINDINGS_FENCE_INFO = "json redaction-recommendation-bindings"
_BINDINGS_RE = re.compile(
    r"```json redaction-recommendation-bindings\n(.*?)\n```",
    re.DOTALL,
)
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REVIEWED_AT_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$"
)

_ARTIFACT_DIR_REL = "artifacts/redaction-evaluation"
_HOSTED_RECEIPT_NAME = "hosted-validation-receipt.json"
_DEFAULT_SCHEMA_REL = (
    Path("tests") / "redaction_evaluation" / "schema" / "adversarial-review.schema.json"
)


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Recommendation machine bindings
# ---------------------------------------------------------------------------


def render_bindings_block(bindings: Mapping[str, Any]) -> str:
    """Render the canonical fenced machine-bindings block."""

    body = json.dumps(bindings, indent=2, sort_keys=True, ensure_ascii=True)
    return f"```{BINDINGS_FENCE_INFO}\n{body}\n```"


def parse_recommendation_bindings(text: str) -> dict[str, Any]:
    """Extract and parse the machine-bindings block from recommendation text.

    Raises ``ValueError`` when the block is missing, duplicated, or does not
    contain a JSON object.
    """

    matches = _BINDINGS_RE.findall(text)
    if not matches:
        raise ValueError("recommendation machine-bindings block is missing")
    if len(matches) > 1:
        raise ValueError("recommendation contains multiple machine-bindings blocks")
    try:
        parsed = json.loads(matches[0])
    except ValueError as error:
        raise ValueError(
            f"recommendation machine-bindings block is not valid JSON: {error}"
        ) from error
    if not isinstance(parsed, dict):
        raise ValueError("recommendation machine-bindings block must be a JSON object")
    return parsed


def replace_bindings_block(text: str, bindings: Mapping[str, Any]) -> str:
    """Rewrite only the fenced bindings block, leaving all prose untouched.

    When no block exists yet, a ``## Machine bindings`` section holding the
    block is appended (one-time bootstrap; subsequent calls replace in
    place).
    """

    block = render_bindings_block(bindings)
    if _BINDINGS_RE.search(text):
        return _BINDINGS_RE.sub(lambda _match: block, text, count=1)
    section = (
        "\n## Machine bindings\n\n"
        "Mechanically written by `python scripts/evaluate_redaction_backends.py "
        "bind-recommendation` and verified by the `verify` step; the values "
        "below must equal the regenerated evidence.\n\n"
    )
    if not text.endswith("\n"):
        text += "\n"
    return text + section + block + "\n"


def strip_bindings_block(text: str) -> str:
    """Return the recommendation text with the machine-bindings block removed."""

    return _BINDINGS_RE.sub("", text)


def verify_recommendation_bindings(
    text: str, expected: Mapping[str, Any]
) -> list[str]:
    """Compare the committed bindings block against the regenerated truth."""

    try:
        actual = parse_recommendation_bindings(text)
    except ValueError as error:
        return [str(error)]
    errors: list[str] = []
    for key in sorted(set(expected) | set(actual)):
        if key not in actual:
            errors.append(f"recommendation bindings: missing key: {key}")
        elif key not in expected:
            errors.append(f"recommendation bindings: unexpected key: {key}")
        elif actual[key] != expected[key]:
            errors.append(f"recommendation bindings: value drift at key: {key}")
    return errors


# ---------------------------------------------------------------------------
# Review checks
# ---------------------------------------------------------------------------


def make_check(
    check_id: str,
    status: str,
    evidence_refs: list[str],
    *,
    affected_candidate_ids: list[str] | None = None,
    affected_record_ids: list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Schema-shaped review check entry (``raw_values_included`` locked false)."""

    check: dict[str, Any] = {
        "check_id": check_id,
        "status": status,
        "evidence_refs": evidence_refs,
        "affected_candidate_ids": sorted(affected_candidate_ids or []),
        "affected_record_ids": sorted(affected_record_ids or []),
        "raw_values_included": False,
    }
    if notes:
        check["notes"] = notes[:2000]
    return check


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _ref(name: str) -> str:
    return f"{_ARTIFACT_DIR_REL}/{name}"


def _compare_check(
    check_id: str,
    out_dir: Path,
    regenerated: Mapping[str, str],
    filenames: list[str],
) -> dict[str, Any]:
    """One reproduction check: committed files must equal regenerated bytes."""

    missing: list[str] = []
    drifted: list[str] = []
    unavailable: list[str] = []
    for name in filenames:
        expected = regenerated.get(name)
        if expected is None:
            unavailable.append(name)
            continue
        path = out_dir / name
        if not path.is_file():
            missing.append(name)
        elif path.read_bytes() != expected.encode("utf-8"):
            drifted.append(name)
    if missing or drifted:
        notes = "; ".join(
            [f"missing: {n}" for n in missing] + [f"drift: {n}" for n in drifted]
        )
        return make_check(
            check_id, "failed", [_ref(name) for name in filenames], notes=notes
        )
    if unavailable:
        return make_check(
            check_id,
            "not_applicable",
            [_ref(name) for name in filenames],
            notes="could not regenerate: " + "; ".join(unavailable),
        )
    return make_check(check_id, "passed", [_ref(name) for name in filenames])


def _gate_check(
    check_id: str,
    gates_doc: Any,
    gate_id: str,
    evidence: list[str],
) -> dict[str, Any]:
    """Check one named hard gate is ``passed`` for every candidate."""

    if not isinstance(gates_doc, dict) or not isinstance(
        gates_doc.get("candidates"), list
    ):
        return make_check(
            check_id, "not_applicable", evidence, notes="hard-gates.json unavailable"
        )
    offenders: list[str] = []
    for candidate in gates_doc["candidates"]:
        if not isinstance(candidate, dict):
            continue
        statuses = {
            str(gate.get("gate_id")): gate.get("status")
            for gate in candidate.get("gates", [])
            if isinstance(gate, dict)
        }
        if statuses.get(gate_id) != "passed":
            offenders.append(str(candidate.get("candidate_id")))
    if offenders:
        return make_check(
            check_id,
            "failed",
            evidence,
            affected_candidate_ids=offenders,
            notes=f"gate {gate_id} not passed for: {', '.join(sorted(offenders))}",
        )
    return make_check(check_id, "passed", evidence)


def run_review_checks(
    out_dir: Path,
    *,
    corpus_errors: list[str],
    regenerated: Mapping[str, str],
    binding_errors: list[str],
    merge_errors: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Execute the standard review checks against a committed artifact set.

    ``regenerated`` maps artifact filename to the freshly regenerated
    canonical text (from the orchestrator's verify machinery);
    ``corpus_errors``, ``binding_errors``, and ``merge_errors`` are the
    outcomes of the corpus, recommendation-binding, and external-verdict
    merge verifications, all actually executed by the caller.
    """

    merge_errors = merge_errors or []

    out_dir = Path(out_dir)
    gates_doc = _load_json(out_dir / "hard-gates.json")
    matrix_doc = _load_json(out_dir / "candidate-matrix.json")
    checks: list[dict[str, Any]] = []

    checks.append(
        make_check(
            "corpus-digests-verified",
            "passed" if not corpus_errors else "failed",
            [
                "tests/redaction_evaluation/corpus-manifest.json",
                _ref("corpus-manifest.json"),
            ],
            notes="; ".join(corpus_errors[:5]) if corpus_errors else None,
        )
    )
    checks.append(
        _compare_check(
            "aggregates-reproduce",
            out_dir,
            regenerated,
            [
                "metrics.json",
                "entity-results.csv",
                "hard-gates.json",
                "candidate-matrix.json",
                "evaluation-input.json",
            ],
        )
    )
    checks.append(
        _compare_check(
            "weighted-scores-reproduce", out_dir, regenerated, ["weighted-scores.json"]
        )
    )
    checks.append(
        _compare_check(
            "artifact-manifest-clean", out_dir, regenerated, ["artifact-manifest.json"]
        )
    )
    checks.append(
        make_check(
            "recommendation-bindings-verified",
            "passed" if not binding_errors else "failed",
            [_ref("recommendation.md")],
            notes="; ".join(binding_errors[:5]) if binding_errors else None,
        )
    )
    checks.append(
        make_check(
            "external-verdicts-merged",
            "passed" if not merge_errors else "failed",
            [
                _ref("candidate-results"),
                _ref("offline-proof.json"),
                _ref("license-report.json"),
            ],
            notes="; ".join(merge_errors[:5]) if merge_errors else None,
        )
    )

    # Eligibility: selection_eligible and hard_gates_passed must both mirror
    # the all-gates-passed derivation for every candidate.
    if isinstance(gates_doc, dict) and isinstance(matrix_doc, dict):
        gate_map = {
            str(c.get("candidate_id")): c
            for c in gates_doc.get("candidates", [])
            if isinstance(c, dict)
        }
        matrix_map = {
            str(c.get("candidate_id")): c
            for c in matrix_doc.get("candidates", [])
            if isinstance(c, dict)
        }
        offenders = []
        for candidate_id in sorted(set(gate_map) | set(matrix_map)):
            gate_entry = gate_map.get(candidate_id, {})
            matrix_entry = matrix_map.get(candidate_id, {})
            _state, all_passed, _pending, _failed = derive_gate_aggregate(
                gate_entry.get("gates", [])
            )
            if (
                matrix_entry.get("selection_eligible") is not all_passed
                or matrix_entry.get("hard_gates_passed") is not all_passed
                or gate_entry.get("passed") is not all_passed
            ):
                offenders.append(candidate_id)
        checks.append(
            make_check(
                "eligibility-consistency",
                "failed" if offenders else "passed",
                [_ref("hard-gates.json"), _ref("candidate-matrix.json")],
                affected_candidate_ids=offenders,
                notes=(
                    "selection_eligible must equal all-gates-passed; offenders: "
                    + ", ".join(offenders)
                    if offenders
                    else None
                ),
            )
        )
    else:
        checks.append(
            make_check(
                "eligibility-consistency",
                "not_applicable",
                [_ref("hard-gates.json"), _ref("candidate-matrix.json")],
                notes="hard-gates.json or candidate-matrix.json unavailable",
            )
        )

    # Hard-gate states recorded, naming pending gates per candidate.
    if isinstance(gates_doc, dict) and isinstance(gates_doc.get("candidates"), list):
        pending_notes: list[str] = []
        malformed: list[str] = []
        for candidate in gates_doc["candidates"]:
            if not isinstance(candidate, dict):
                continue
            candidate_id = str(candidate.get("candidate_id"))
            gates = candidate.get("gates")
            if not isinstance(gates, list) or not gates:
                malformed.append(candidate_id)
                continue
            _state, _passed, pending, _failed = derive_gate_aggregate(gates)
            pending_notes.append(
                f"{candidate_id}: pending=[{', '.join(pending) if pending else '-'}]"
            )
        checks.append(
            make_check(
                "hard-gate-states-recorded",
                "failed" if malformed else "passed",
                [_ref("hard-gates.json")],
                affected_candidate_ids=malformed,
                notes="; ".join(pending_notes) or None,
            )
        )
    else:
        checks.append(
            make_check(
                "hard-gate-states-recorded",
                "not_applicable",
                [_ref("hard-gates.json")],
                notes="hard-gates.json unavailable",
            )
        )

    # Determinism: repeated-run mismatches must be empty in every candidate
    # result and the deterministic-output gate must have passed.
    results_dir = out_dir / "candidate-results"
    result_paths = sorted(results_dir.glob("*.json")) if results_dir.is_dir() else []
    if result_paths:
        offenders = []
        for path in result_paths:
            result = _load_json(path)
            if not isinstance(result, dict):
                offenders.append(path.stem)
                continue
            mismatched = (result.get("determinism") or {}).get(
                "mismatched_record_ids", []
            )
            if mismatched:
                offenders.append(str(result.get("candidate_id")))
        determinism_gate = _gate_check(
            "determinism-clean",
            gates_doc,
            "deterministic-output",
            [_ref("candidate-results"), _ref("hard-gates.json")],
        )
        if offenders and determinism_gate["status"] == "passed":
            determinism_gate = make_check(
                "determinism-clean",
                "failed",
                [_ref("candidate-results"), _ref("hard-gates.json")],
                affected_candidate_ids=offenders,
                notes="repeated-output mismatches recorded for: "
                + ", ".join(sorted(offenders)),
            )
        checks.append(determinism_gate)
    else:
        checks.append(
            make_check(
                "determinism-clean",
                "not_applicable",
                [_ref("candidate-results"), _ref("hard-gates.json")],
                notes="candidate results unavailable",
            )
        )

    # Offline proof: every candidate ran with zero undeclared connections.
    offline_doc = _load_json(out_dir / "offline-proof.json")
    if isinstance(offline_doc, dict) and isinstance(
        offline_doc.get("candidates"), list
    ):
        offenders = []
        for entry in offline_doc["candidates"]:
            if not isinstance(entry, dict):
                continue
            if entry.get("passed") is not True or entry.get("attempted_connections"):
                offenders.append(str(entry.get("candidate_id")))
        checks.append(
            make_check(
                "offline-proof-clean",
                "failed" if offenders else "passed",
                [_ref("offline-proof.json")],
                affected_candidate_ids=offenders,
                notes=(
                    "offline proof not clean for: " + ", ".join(sorted(offenders))
                    if offenders
                    else None
                ),
            )
        )
    else:
        checks.append(
            make_check(
                "offline-proof-clean",
                "not_applicable",
                [_ref("offline-proof.json")],
                notes="offline-proof.json unavailable",
            )
        )

    checks.append(
        _gate_check(
            "no-raw-leakage-gate",
            gates_doc,
            "no-raw-leakage",
            [_ref("hard-gates.json")],
        )
    )
    checks.append(
        _gate_check(
            "receipt-validation-gate",
            gates_doc,
            "receipt-contract-compatible",
            [_ref("hard-gates.json")],
        )
    )
    return checks


# ---------------------------------------------------------------------------
# Review document assembly
# ---------------------------------------------------------------------------


def _derive_discrepancies(
    checks: list[dict[str, Any]], gates_doc: Any
) -> list[dict[str, Any]]:
    discrepancies: list[dict[str, Any]] = []
    for check in checks:
        if check["status"] != "failed":
            continue
        discrepancies.append(
            {
                "discrepancy_id": f"check-failed-{check['check_id']}",
                "severity": "blocker",
                "summary": (
                    f"review check {check['check_id']} failed: "
                    + str(check.get("notes", "see check entry"))
                )[:1000],
                "evidence_refs": list(check["evidence_refs"]),
                "candidate_ids": list(check["affected_candidate_ids"]),
                "record_ids": [],
                "implementation_required": True,
                "owner_decision_required": False,
            }
        )
    if isinstance(gates_doc, dict):
        for candidate in gates_doc.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            candidate_id = str(candidate.get("candidate_id"))
            _state, _passed, pending, _failed = derive_gate_aggregate(
                candidate.get("gates", [])
            )
            if not pending:
                continue
            discrepancies.append(
                {
                    "discrepancy_id": f"license-review-pending-{candidate_id}",
                    "severity": "high",
                    "summary": (
                        f"{candidate_id} has pending hard gate(s) "
                        f"[{', '.join(pending)}] awaiting an explicit owner "
                        "call; the candidate is not selection-eligible until "
                        "resolved."
                    ),
                    "evidence_refs": [
                        _ref("hard-gates.json"),
                        _ref("license-report.json"),
                    ],
                    "candidate_ids": [candidate_id],
                    "record_ids": [],
                    "implementation_required": False,
                    "owner_decision_required": True,
                }
            )
    return discrepancies


def build_adversarial_review(
    out_dir: Path,
    *,
    pr_number: int,
    head_sha: str,
    base_ref: str,
    reviewed_at: str,
    checks: list[dict[str, Any]],
    schema_path: Path | None = None,
) -> dict[str, Any]:
    """Assemble and schema-validate the exact-head adversarial review.

    Raises ``ValueError`` when required identity inputs are malformed, when
    the committed artifact set cannot supply the corpus/bundle digests, or
    when the assembled document does not validate against the adversarial
    review schema (the caller must refuse to write in that case).
    """

    out_dir = Path(out_dir)
    head = head_sha.strip().lower()
    if not _GIT_SHA_RE.fullmatch(head):
        raise ValueError("head_sha must be a full 40-character lowercase git SHA")
    if not _REVIEWED_AT_RE.fullmatch(reviewed_at):
        raise ValueError(
            "reviewed_at must be an explicit UTC timestamp like "
            "2026-07-24T00:00:00Z (no implicit now())"
        )

    matrix_doc = _load_json(out_dir / "candidate-matrix.json")
    if not isinstance(matrix_doc, dict) or not isinstance(
        matrix_doc.get("candidates"), list
    ):
        raise ValueError("candidate-matrix.json unavailable; cannot identify review")
    candidate_ids = sorted(
        str(candidate.get("candidate_id"))
        for candidate in matrix_doc["candidates"]
        if isinstance(candidate, dict)
    )
    corpus_digests = {
        str(candidate.get("corpus_digest"))
        for candidate in matrix_doc["candidates"]
        if isinstance(candidate, dict)
    }
    if len(corpus_digests) != 1:
        raise ValueError(
            "candidate-matrix.json must carry exactly one corpus digest, found: "
            + ", ".join(sorted(corpus_digests))
        )
    corpus_sha256 = corpus_digests.pop()

    manifest_path = out_dir / "artifact-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("artifact-manifest.json missing; cannot bind artifact bundle")
    artifact_bundle_sha256 = _sha256_bytes(manifest_path.read_bytes())

    gates_doc = _load_json(out_dir / "hard-gates.json")
    discrepancies = _derive_discrepancies(checks, gates_doc)

    failed = any(check["status"] == "failed" for check in checks)
    blockers = any(item["severity"] == "blocker" for item in discrepancies)
    unverifiable = any(check["status"] == "not_applicable" for check in checks)
    if failed or blockers:
        verdict = "not_reviewable"
    elif unverifiable:
        verdict = "reviewable"
    else:
        verdict = "owner_decision_ready"

    evidence_refs = sorted(
        {ref for check in checks for ref in check["evidence_refs"]}
    )
    if (out_dir / _HOSTED_RECEIPT_NAME).is_file():
        evidence_refs.append(_ref(_HOSTED_RECEIPT_NAME))
        evidence_refs = sorted(set(evidence_refs))

    document: dict[str, Any] = {
        "schema_version": 1,
        "review_id": f"adr-0020-exact-head-review-{head[:12]}",
        "reviewed_pr": {
            "repository": REPOSITORY,
            "number": pr_number,
            "head_sha": head,
            "base_ref": base_ref,
        },
        "parent_baseline": {
            "pr_number": PARENT_BASELINE_PR,
            "head_sha": PARENT_BASELINE_HEAD,
        },
        "corpus_sha256": corpus_sha256,
        "artifact_bundle_sha256": artifact_bundle_sha256,
        "candidate_ids": candidate_ids,
        "verdict": verdict,
        "checks": checks,
        "unresolved_discrepancies": discrepancies,
        "evidence_refs": evidence_refs,
        "raw_values_included": False,
        "reviewed_at": reviewed_at,
    }

    if schema_path is None:
        schema_path = Path(__file__).resolve().parents[2] / _DEFAULT_SCHEMA_REL
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    jsonschema = importlib.import_module("jsonschema")
    validator = jsonschema.Draft202012Validator(schema)
    schema_errors = [
        f"{'.'.join(str(part) for part in error.absolute_path) or '$'}: "
        f"{error.message}"
        for error in sorted(validator.iter_errors(document), key=str)
    ]
    if schema_errors:
        raise ValueError(
            "adversarial review failed schema validation; refusing to write: "
            + "; ".join(schema_errors[:10])
        )
    return document
