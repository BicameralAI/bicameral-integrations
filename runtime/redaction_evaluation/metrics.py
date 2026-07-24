# SPDX-License-Identifier: MIT
"""Candidate-neutral metric calculation for the ADR-0020 redaction spike.

Implements the matching rules and metric definitions from the evaluation
contract (``_review-scratch/adr0020/design-corpus.md``):

- a candidate finding and an expected entity are matchable when their field
  paths match, their normalized categories are equal, and their spans overlap
  by at least one character;
- deterministic maximum-overlap greedy 1:1 assignment, ordered by
  ``(overlap desc, expected.start asc, candidate.start asc, entity_id asc)``;
- TP = matched pairs, FP = unmatched candidate findings, FN = unmatched
  expected entities; exact-span matches reported separately;
- ``precision = TP/(TP+FP)``, ``recall = TP/(TP+FN)``,
  ``F1 = 2PR/(P+R)``, ``F2 = 5PR/(4P+R)``; a zero denominator emits ``null``
  plus a typed explanation, never a silent 0 or 1.

Raw corpus values are read only in memory (destructive-false-positive
occurrence checks); every emitted number is value-free.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Sequence

_DIMENSIONS = ("total", "category", "subtype", "source_shape", "class")


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def overlap_length(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    """Character overlap of two half-open spans (0 when disjoint)."""

    return max(0, min(a_end, b_end) - max(a_start, b_start))


def match_findings(
    candidate_findings: Sequence[dict[str, Any]],
    expected_entities: Sequence[dict[str, Any]],
) -> tuple[
    list[tuple[dict[str, Any], dict[str, Any]]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Deterministic maximum-overlap 1:1 matching for ONE (record, field).

    Returns ``(matched_pairs, unmatched_candidates, unmatched_expected)``
    where each pair is ``(candidate_finding, expected_entity)``.
    """

    pairs: list[tuple[int, int, int, str, int, int]] = []
    for c_index, candidate in enumerate(candidate_findings):
        for e_index, expected in enumerate(expected_entities):
            if candidate["category"] != expected["category"]:
                continue
            overlap = overlap_length(
                candidate["start"], candidate["end"], expected["start"], expected["end"]
            )
            if overlap < 1:
                continue
            pairs.append(
                (
                    -overlap,
                    expected["start"],
                    candidate["start"],
                    str(expected["entity_id"]),
                    c_index,
                    e_index,
                )
            )
    pairs.sort()
    used_candidates: set[int] = set()
    used_expected: set[int] = set()
    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for _neg_overlap, _e_start, _c_start, _entity_id, c_index, e_index in pairs:
        if c_index in used_candidates or e_index in used_expected:
            continue
        used_candidates.add(c_index)
        used_expected.add(e_index)
        matches.append((candidate_findings[c_index], expected_entities[e_index]))
    unmatched_candidates = [
        finding
        for index, finding in enumerate(candidate_findings)
        if index not in used_candidates
    ]
    unmatched_expected = [
        entity
        for index, entity in enumerate(expected_entities)
        if index not in used_expected
    ]
    return matches, unmatched_candidates, unmatched_expected


# ---------------------------------------------------------------------------
# Ratio helpers with the zero-denominator rule
# ---------------------------------------------------------------------------


def safe_ratio(numerator: int, denominator: int, note: str) -> tuple[float | None, str | None]:
    if denominator == 0:
        return None, note
    return numerator / denominator, None


def f_beta(
    precision: float | None, recall: float | None, beta_squared: float
) -> tuple[float | None, str | None]:
    if precision is None or recall is None:
        return None, "undefined_precision_or_recall"
    denominator = beta_squared * precision + recall
    if denominator == 0:
        return None, "precision_and_recall_zero"
    return (1 + beta_squared) * precision * recall / denominator, None


def finalize_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    """Attach precision/recall/F1/F2 (+ typed notes) to a tp/fp/fn bucket."""

    tp, fp, fn = bucket["tp"], bucket["fp"], bucket["fn"]
    precision, precision_note = safe_ratio(tp, tp + fp, "no_positive_predictions")
    recall, recall_note = safe_ratio(tp, tp + fn, "no_expected_entities")
    f1, f1_note = f_beta(precision, recall, 1.0)
    f2, f2_note = f_beta(precision, recall, 4.0)
    exact_accuracy, exact_note = safe_ratio(
        bucket["exact_span"], tp, "no_true_positives"
    )
    bucket.update(
        {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "f2": f2,
            "exact_span_accuracy": exact_accuracy,
        }
    )
    for key, note in (
        ("precision_note", precision_note),
        ("recall_note", recall_note),
        ("f1_note", f1_note),
        ("f2_note", f2_note),
        ("exact_span_accuracy_note", exact_note),
    ):
        if note is not None:
            bucket[key] = note
    return bucket


def _new_bucket() -> dict[str, Any]:
    return {"tp": 0, "fp": 0, "fn": 0, "exact_span": 0}


# ---------------------------------------------------------------------------
# Metric computation over one candidate result document
# ---------------------------------------------------------------------------


def _corpus_loader() -> Any:
    return importlib.import_module("tests.redaction_evaluation.corpus_loader")


def _load_expected(repo_root: Path, expected_path: str) -> dict[str, Any]:
    with (repo_root / expected_path).open("r", encoding="utf-8") as handle:
        data: dict[str, Any] = json.load(handle)
    return data


def _resolve_field(observation: dict[str, Any], field_path: str) -> str | None:
    from .runner import resolve_path

    try:
        value = resolve_path(observation, field_path)
    except KeyError:
        return None
    return value if isinstance(value, str) else None


def _substring_spans(text: str, needle: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    if not needle:
        return spans
    index = text.find(needle)
    while index != -1:
        spans.append((index, index + len(needle)))
        index = text.find(needle, index + 1)
    return spans


def compute_metrics(candidate_result: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    """Aggregate quality/preservation/security metrics for one candidate run."""

    repo_root = Path(repo_root)
    loader = _corpus_loader()
    manifest_path = repo_root / "tests" / "redaction_evaluation" / "corpus-manifest.json"
    manifest_by_id: dict[str, dict[str, Any]] = {
        str(record["record_id"]): record
        for record in loader.iter_manifest(manifest_path)
    }

    totals = _new_bucket()
    by_category: dict[str, dict[str, Any]] = {}
    by_subtype: dict[str, dict[str, Any]] = {}
    by_source_shape: dict[str, dict[str, Any]] = {}
    by_class: dict[str, dict[str, Any]] = {}

    def _buckets_for(
        record: dict[str, Any], category: str | None, subtype: str | None
    ) -> list[dict[str, Any]]:
        buckets = [totals]
        if category is not None:
            buckets.append(by_category.setdefault(category, _new_bucket()))
        if subtype is not None:
            buckets.append(by_subtype.setdefault(subtype, _new_bucket()))
        buckets.append(
            by_source_shape.setdefault(record["source_shape"], _new_bucket())
        )
        for record_class in record.get("classes", []):
            buckets.append(by_class.setdefault(record_class, _new_bucket()))
        return buckets

    destructive_false_positives = 0
    clean_records_modified = 0
    protected_field_mutations = 0
    post_screen_escapes = 0
    schema_failures = 0
    outcome_mismatch_record_ids: list[str] = []
    mandatory_entities_protected = 0
    preservation_records = 0
    preservation_passed = 0
    preservation_failed_ids: list[str] = []
    agreement_records = 0
    agreement_matches = 0
    agreement_mismatched_ids: list[str] = []

    for record in candidate_result.get("records", []):
        record_id = str(record["record_id"])
        manifest_record = manifest_by_id.get(record_id)
        if manifest_record is None:
            continue
        expected = _load_expected(repo_root, str(manifest_record["expected_path"]))
        input_record = loader.load_input_record(
            repo_root / str(manifest_record["input_path"])
        )
        observation: dict[str, Any] = input_record.get("observation") or {}
        expected_outcome = expected.get("expected_outcome")
        actual_outcome = record.get("outcome")
        is_negative_control = "negative_control" in record.get("classes", [])

        post_screen_escapes += int(record.get("post_screen_hits", 0) or 0)
        if record.get("structural_mirror_ok") is False:
            schema_failures += 1

        # Protected identity fields.
        record_protected_ok = True
        identity_digests = record.get("identity_digests") or {}
        for protected in expected.get("protected_fields", []):
            actual_digest = identity_digests.get(protected["field_path"])
            if actual_digest != protected["expected_value_sha256"]:
                protected_field_mutations += 1
                record_protected_ok = False

        # Expected-outcome agreement for failed-closed expectations.
        if expected_outcome == "failed_closed":
            agreement_records += 1
            if actual_outcome == "failed_closed" and record.get(
                "failure_reason"
            ) == expected.get("expected_failure_reason"):
                agreement_matches += 1
            else:
                agreement_mismatched_ids.append(record_id)
            continue

        # Detection metrics apply only to sanitized/unchanged expectations.
        if expected_outcome not in ("sanitized", "unchanged"):
            continue

        entities = list(expected.get("expected_entities", []))

        if actual_outcome == "failed_closed":
            # Outcome mismatch: the candidate produced no usable sanitized
            # output. Every expected entity counts as a false negative; the
            # candidate's findings are not counted as false positives.
            # Mandatory entities are still PROTECTED (fail-closed emits
            # nothing), which is tracked separately from detection quality.
            outcome_mismatch_record_ids.append(record_id)
            if is_negative_control:
                clean_records_modified += 1
            mandatory_entities_protected += sum(
                1 for entity in entities if entity.get("mandatory")
            )
            for entity in entities:
                for bucket in _buckets_for(
                    record, entity["category"], entity["subtype"]
                ):
                    bucket["fn"] += 1
            if expected.get("preservation_assertions"):
                preservation_records += 1
                preservation_failed_ids.append(record_id)
            continue

        findings = list(record.get("findings", []))
        field_paths = sorted(
            {f["field_path"] for f in findings}
            | {e["field_path"] for e in entities}
        )
        record_fps: list[dict[str, Any]] = []
        for field_path in field_paths:
            field_findings = [f for f in findings if f["field_path"] == field_path]
            field_entities = [e for e in entities if e["field_path"] == field_path]
            matches, fps, fns = match_findings(field_findings, field_entities)
            for candidate_finding, expected_entity in matches:
                exact = (
                    candidate_finding["start"] == expected_entity["start"]
                    and candidate_finding["end"] == expected_entity["end"]
                )
                for bucket in _buckets_for(
                    record, expected_entity["category"], expected_entity["subtype"]
                ):
                    bucket["tp"] += 1
                    if exact:
                        bucket["exact_span"] += 1
            for finding in fps:
                record_fps.append(finding)
                for bucket in _buckets_for(
                    record, finding["category"], finding["subtype"]
                ):
                    bucket["fp"] += 1
            for entity in fns:
                for bucket in _buckets_for(
                    record, entity["category"], entity["subtype"]
                ):
                    bucket["fn"] += 1

        # Destructive false positives: an FP on a negative-control record, or
        # an FP overlapping an occurrence of a required preservation substring
        # in the input field text.
        assertions = expected.get("preservation_assertions", [])
        for finding in record_fps:
            if is_negative_control:
                destructive_false_positives += 1
                continue
            destructive = False
            for assertion in assertions:
                if assertion["field_path"] != finding["field_path"]:
                    continue
                field_text = _resolve_field(observation, assertion["field_path"])
                if field_text is None:
                    continue
                for span_start, span_end in _substring_spans(
                    field_text, assertion["required_substring"]
                ):
                    if overlap_length(
                        finding["start"], finding["end"], span_start, span_end
                    ):
                        destructive = True
                        break
                if destructive:
                    break
            if destructive:
                destructive_false_positives += 1

        if is_negative_control and actual_outcome != "unchanged":
            clean_records_modified += 1

        # Decision preservation per the evaluation contract: every required
        # substring survived sanitization (runner evaluated this while the
        # sanitized text was in memory), the record still produced usable
        # output (a fail-closed rejection destroys the decision content),
        # and no protected field mutated. A detection miss that leaves the
        # clause untouched still preserves the decision; the miss itself is
        # already charged as a false negative.
        if assertions:
            preservation_records += 1
            preservation_block = record.get("preservation") or {}
            missing = preservation_block.get("missing_assertion_ids")
            assertions_ok = (
                preservation_block.get("assertions_checked") == len(assertions)
                and missing == []
            )
            if (
                assertions_ok
                and actual_outcome in ("sanitized", "unchanged")
                and record_protected_ok
            ):
                preservation_passed += 1
            else:
                preservation_failed_ids.append(record_id)

    determinism = candidate_result.get("determinism", {})
    repeated_output_mismatches = len(determinism.get("mismatched_record_ids", []))

    preservation_ratio, preservation_note = safe_ratio(
        preservation_passed, preservation_records, "no_preservation_records"
    )
    preservation_doc: dict[str, Any] = {
        "destructive_false_positives": destructive_false_positives,
        "clean_records_modified": clean_records_modified,
        "protected_field_mutations": protected_field_mutations,
        "decision_preservation": {
            "records_evaluated": preservation_records,
            "passed": preservation_passed,
            "failed_record_ids": sorted(preservation_failed_ids),
            "pass_ratio": preservation_ratio,
        },
    }
    if preservation_note is not None:
        preservation_doc["decision_preservation"]["pass_ratio_note"] = (
            preservation_note
        )

    return {
        "schema_version": 1,
        "candidate_id": candidate_result["candidate_id"],
        "corpus_digest": candidate_result.get("corpus_digest"),
        "totals": finalize_bucket(totals),
        "by_category": {
            key: finalize_bucket(bucket)
            for key, bucket in sorted(by_category.items())
        },
        "by_subtype": {
            key: finalize_bucket(bucket)
            for key, bucket in sorted(by_subtype.items())
        },
        "by_source_shape": {
            key: finalize_bucket(bucket)
            for key, bucket in sorted(by_source_shape.items())
        },
        "by_class": {
            key: finalize_bucket(bucket) for key, bucket in sorted(by_class.items())
        },
        "preservation": preservation_doc,
        "security": {
            "post_screen_escapes": post_screen_escapes,
            "schema_failures": schema_failures,
            "repeated_output_mismatches": repeated_output_mismatches,
            "outcome_mismatch_record_ids": sorted(outcome_mismatch_record_ids),
            "mandatory_entities_protected_on_failure": mandatory_entities_protected,
            "expected_outcome_agreement": {
                "records": agreement_records,
                "matches": agreement_matches,
                "mismatched_record_ids": sorted(agreement_mismatched_ids),
            },
        },
    }


# ---------------------------------------------------------------------------
# Flat rows for entity-results.csv
# ---------------------------------------------------------------------------


def _notes_for(bucket: dict[str, Any]) -> str:
    notes = [
        f"{key.removesuffix('_note')}={bucket[key]}"
        for key in (
            "precision_note",
            "recall_note",
            "f1_note",
            "f2_note",
            "exact_span_accuracy_note",
        )
        if key in bucket
    ]
    return ";".join(notes)


def _row(
    candidate_id: str,
    dimension: str,
    dimension_value: str,
    category: str,
    bucket: dict[str, Any],
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "dimension": dimension,
        "dimension_value": dimension_value,
        "category": category,
        "tp": bucket["tp"],
        "fp": bucket["fp"],
        "fn": bucket["fn"],
        "precision": bucket["precision"],
        "recall": bucket["recall"],
        "f1": bucket["f1"],
        "f2": bucket["f2"],
        "exact_span": bucket["exact_span"],
        "notes": _notes_for(bucket),
    }


def entity_results_rows(metrics_docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stable-ordered flat rows for ``entity-results.csv``."""

    rows: list[dict[str, Any]] = []
    for doc in sorted(metrics_docs, key=lambda d: str(d["candidate_id"])):
        candidate_id = str(doc["candidate_id"])
        rows.append(_row(candidate_id, "total", "all", "", doc["totals"]))
        dimension_sources: list[tuple[str, dict[str, dict[str, Any]], bool]] = [
            ("category", doc.get("by_category", {}), True),
            ("subtype", doc.get("by_subtype", {}), False),
            ("source_shape", doc.get("by_source_shape", {}), False),
            ("class", doc.get("by_class", {}), False),
        ]
        for dimension, source, value_is_category in dimension_sources:
            for value in sorted(source):
                rows.append(
                    _row(
                        candidate_id,
                        dimension,
                        value,
                        value if value_is_category else "",
                        source[value],
                    )
                )
    return rows
