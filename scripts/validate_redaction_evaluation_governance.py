# SPDX-License-Identifier: MIT
"""Validate ADR-0020 adversarial review and owner-decision artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from jsonschema.exceptions import SchemaError, ValidationError  # type: ignore[import-untyped]

_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_DIR = Path("tests/redaction_evaluation/schema")
_ARTIFACT_DIR = Path("artifacts/redaction-evaluation")
_REVIEW_SCHEMA = "adversarial-review.schema.json"
_DECISION_SCHEMA = "owner-decision-packet.schema.json"
_REVIEW_ARTIFACT = "adversarial-review.json"
_DECISION_ARTIFACT = "owner-decision.json"


def _load_json(path: Path, label: str, errors: list[str]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label}: file not found: {path}")
    except UnicodeDecodeError:
        errors.append(f"{label}: file is not valid UTF-8: {path}")
    except json.JSONDecodeError:
        errors.append(f"{label}: file is not valid JSON: {path}")
    return None


def _sha256_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _location(error: ValidationError) -> str:
    result = "$"
    for part in error.absolute_path:
        result += f"[{part}]" if isinstance(part, int) else f".{part}"
    return result


def _schema_errors(
    validator: Draft202012Validator,
    value: Any,
    label: str,
) -> list[str]:
    return [
        f"{label}: schema violation at {_location(error)} (validator={error.validator})"
        for error in sorted(
            validator.iter_errors(value),
            key=lambda item: tuple(str(part) for part in item.absolute_path),
        )
    ]


def _duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def _validate_review(review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    checks = review.get("checks", [])
    check_ids = [item.get("check_id", "") for item in checks if isinstance(item, dict)]
    for duplicate in _duplicates(check_ids):
        errors.append(f"adversarial review: duplicate check_id: {duplicate}")

    discrepancies = review.get("unresolved_discrepancies", [])
    discrepancy_ids = [
        item.get("discrepancy_id", "") for item in discrepancies if isinstance(item, dict)
    ]
    for duplicate in _duplicates(discrepancy_ids):
        errors.append(f"adversarial review: duplicate discrepancy_id: {duplicate}")

    if review.get("verdict") == "owner_decision_ready":
        failed_checks = [
            item.get("check_id", "<unknown>")
            for item in checks
            if isinstance(item, dict) and item.get("status") == "failed"
        ]
        if failed_checks:
            errors.append(
                "adversarial review: owner_decision_ready cannot contain failed checks: "
                + ", ".join(sorted(failed_checks))
            )
        blockers = [
            item.get("discrepancy_id", "<unknown>")
            for item in discrepancies
            if isinstance(item, dict) and item.get("severity") == "blocker"
        ]
        if blockers:
            errors.append(
                "adversarial review: owner_decision_ready cannot contain blockers: "
                + ", ".join(sorted(blockers))
            )
    return errors


def _validate_decision(
    decision: dict[str, Any],
    review: dict[str, Any] | None,
    review_path: Path,
) -> list[str]:
    errors: list[str] = []
    eligible = decision.get("eligible_candidates", [])
    ineligible_items = decision.get("ineligible_candidates", [])
    ineligible = [
        item.get("candidate_id", "")
        for item in ineligible_items
        if isinstance(item, dict)
    ]
    for duplicate in _duplicates(eligible):
        errors.append(f"owner decision: duplicate eligible candidate: {duplicate}")
    for duplicate in _duplicates(ineligible):
        errors.append(f"owner decision: duplicate ineligible candidate: {duplicate}")
    overlap = sorted(set(eligible) & set(ineligible))
    if overlap:
        errors.append(
            "owner decision: candidates cannot be both eligible and ineligible: "
            + ", ".join(overlap)
        )

    summary = decision.get("measured_summary", {})
    scores = summary.get("score_summary", []) if isinstance(summary, dict) else []
    score_ids = [item.get("candidate_id", "") for item in scores if isinstance(item, dict)]
    for duplicate in _duplicates(score_ids):
        errors.append(f"owner decision: duplicate score candidate_id: {duplicate}")

    recommended = summary.get("recommended_candidate_id") if isinstance(summary, dict) else None
    if recommended is not None and recommended not in eligible:
        errors.append("owner decision: recommended candidate must be eligible")

    selected = decision.get("selected_candidate_id")
    if selected is not None and selected not in eligible:
        errors.append("owner decision: selected candidate must be eligible")

    if decision.get("status") == "accepted":
        if review is None:
            errors.append("owner decision: accepted packet requires adversarial review artifact")
        else:
            if review.get("verdict") != "owner_decision_ready":
                errors.append(
                    "owner decision: accepted packet requires owner_decision_ready review"
                )
            expected_digest = (
                decision.get("evidence_bindings", {}).get("adversarial_review_sha256")
            )
            actual_digest = _sha256_file(review_path)
            if expected_digest != actual_digest:
                errors.append("owner decision: adversarial review SHA-256 mismatch")

    if decision.get("release_authority_granted") is not False:
        errors.append("owner decision: release_authority_granted must remain false")
    return errors


def validate_repository(root: Path = _ROOT) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    schema_root = root / _SCHEMA_DIR
    schemas: dict[str, dict[str, Any]] = {}
    for name in (_REVIEW_SCHEMA, _DECISION_SCHEMA):
        value = _load_json(schema_root / name, name, errors)
        if not isinstance(value, dict):
            continue
        try:
            Draft202012Validator.check_schema(value)
        except SchemaError:
            errors.append(f"{name}: invalid Draft 2020-12 schema")
            continue
        schemas[name] = value
    if errors:
        return sorted(errors)

    artifact_root = root / _ARTIFACT_DIR
    review_path = artifact_root / _REVIEW_ARTIFACT
    decision_path = artifact_root / _DECISION_ARTIFACT
    review: dict[str, Any] | None = None

    if review_path.exists():
        value = _load_json(review_path, "adversarial review", errors)
        if isinstance(value, dict):
            review_errors = _schema_errors(
                Draft202012Validator(schemas[_REVIEW_SCHEMA]),
                value,
                "adversarial review",
            )
            errors.extend(review_errors)
            if not review_errors:
                review = value
                errors.extend(_validate_review(value))

    if decision_path.exists():
        value = _load_json(decision_path, "owner decision", errors)
        if isinstance(value, dict):
            decision_errors = _schema_errors(
                Draft202012Validator(schemas[_DECISION_SCHEMA]),
                value,
                "owner decision",
            )
            errors.extend(decision_errors)
            if not decision_errors:
                errors.extend(_validate_decision(value, review, review_path))

    return sorted(set(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_ROOT)
    args = parser.parse_args(argv)
    errors = validate_repository(args.root)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        print(f"\n{len(errors)} redaction governance error(s).", file=sys.stderr)
        return 1
    print("OK: redaction evaluation review and owner-decision governance is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
