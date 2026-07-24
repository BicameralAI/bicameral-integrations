# SPDX-License-Identifier: MIT
"""Governed weighted comparative scoring for the ADR-0020 evaluation.

Moves the previously ad hoc recommendation arithmetic into deterministic
data + code. Weights (out of 100):

- detection F2: 30
- precision and information preservation: 20
- security and failure behavior: 20
- performance and resource cost: 10
- packaging and operational fitness: 10
- maintainability and replacement seam: 10

Every sub-score is a pure function of the committed evaluation artifacts
(``metrics.json``, ``hard-gates.json``, ``benchmark-results.json``,
``memory-isolated.json``) plus the module-level deduction/maintainability
tables below. The weighted score is advisory only: it grants no selection,
release, or deployment authority.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

WEIGHTS: dict[str, float] = {
    "detection": 30.0,
    "precision_preservation": 20.0,
    "security_failure": 20.0,
    "performance_resource": 10.0,
    "packaging_operational": 10.0,
    "maintainability_seam": 10.0,
}

#: Itemized packaging/operational deductions per candidate (points off 10).
PACKAGING_DEDUCTIONS: dict[str, list[dict[str, Any]]] = {
    "bicameral-stdlib-v1": [],
    "presidio-spacy-lg-v1": [
        {
            "points": 1.0,
            "reason": "382MB model wheel provisioning + pinned-URL install step",
        },
        {
            "points": 1.0,
            "reason": "MPL-2.0 certifi flagged review_required in license closure",
        },
    ],
    "presidio-gliner-pii-v1": [
        {
            "points": 2.0,
            "reason": (
                "1.16GB unsigned .bin checkpoint; backbone tokenizer revision "
                "not pinnable through gliner API"
            ),
        },
        {
            "points": 1.0,
            "reason": "HF cache + offline env flags required for offline determinism",
        },
        {
            "points": 1.0,
            "reason": "MPL-2.0 certifi flagged review_required in license closure",
        },
        {
            "points": 1.0,
            "reason": "torch>=2.6 CVE floor must be enforced in packaging",
        },
    ],
    "datafog-regex-v1": [
        {
            "points": 1.0,
            "reason": "LICENSE file vs PyPI classifier inconsistency unresolved",
        },
        {
            "points": 3.0,
            "reason": "fail-closed record loss on every catalog-secret record (measured)",
        },
    ],
}

#: Judged maintainability/replacement-seam score per candidate (out of 10).
MAINTAINABILITY: dict[str, dict[str, Any]] = {
    "bicameral-stdlib-v1": {
        "score": 7.0,
        "reason": (
            "zero deps, in-repo; every new entity class is hand-written regex work"
        ),
    },
    "presidio-spacy-lg-v1": {
        "score": 8.0,
        "reason": (
            "active community project, first-class recognizer API behind the "
            "seam; governance moved to community org 2026-06"
        ),
    },
    "presidio-gliner-pii-v1": {
        "score": 6.0,
        "reason": "gliner pre-1.0 no semver promise; zero-shot labels wording-sensitive",
    },
    "datafog-regex-v1": {
        "score": 5.0,
        "reason": "single-vendor small project; allowlist-only extension surface",
    },
}

_ALLOWED_GATE_STATUSES = ("passed", "pending", "failed")


def derive_gate_aggregate(
    gates: Sequence[Mapping[str, Any]],
) -> tuple[str, bool, list[str], list[str]]:
    """Derive ``(aggregate_state, passed, pending_gate_ids, failed_gate_ids)``.

    Fail-closed: an empty gate list is ``failed``; a gate with an unknown
    status counts as failed. ``passed`` is true only when every gate passed.
    """

    pending = sorted(
        str(gate.get("gate_id")) for gate in gates if gate.get("status") == "pending"
    )
    failed = sorted(
        str(gate.get("gate_id"))
        for gate in gates
        if gate.get("status") not in ("passed", "pending")
    )
    if not gates or failed:
        state = "failed"
    elif pending:
        state = "pending"
    else:
        state = "passed"
    return state, state == "passed", pending, failed


def _candidate_map(document: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Normalize a ``{"candidates": [...] | {...}}`` document to an id map."""

    if not isinstance(document, Mapping):
        return {}
    candidates = document.get("candidates")
    if isinstance(candidates, Mapping):
        return {
            str(candidate_id): dict(entry)
            for candidate_id, entry in candidates.items()
            if isinstance(entry, Mapping)
        }
    if isinstance(candidates, list):
        return {
            str(entry.get("candidate_id")): dict(entry)
            for entry in candidates
            if isinstance(entry, Mapping)
        }
    return {}


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _detection_score(metrics: Mapping[str, Any]) -> float:
    """D1 = 30 * F2 over all entities (0 when F2 is null)."""

    f2 = _as_number(metrics.get("totals", {}).get("f2"))
    return 30.0 * (f2 if f2 is not None else 0.0)


def _precision_preservation_score(metrics: Mapping[str, Any]) -> float:
    """D2 = 10*precision + 10*mean(decision-pass ratio, damage complement).

    The damage complement is ``1 - min(1, (destructive_false_positives +
    clean_records_modified) / 10)``. Null precision or pass ratio counts as 0.
    """

    totals = metrics.get("totals", {})
    preservation = metrics.get("preservation", {})
    decision = preservation.get("decision_preservation", {})
    precision = _as_number(totals.get("precision")) or 0.0
    pass_ratio = _as_number(decision.get("pass_ratio")) or 0.0
    destructive = _as_number(preservation.get("destructive_false_positives")) or 0.0
    clean_modified = _as_number(preservation.get("clean_records_modified")) or 0.0
    damage_complement = 1.0 - min(1.0, (destructive + clean_modified) / 10.0)
    return 10.0 * precision + 10.0 * _mean([pass_ratio, damage_complement])


def _security_score(metrics: Mapping[str, Any]) -> float:
    """D3 = 20 * failure-expectation match ratio, forced to 0 on violations.

    Forced to 0 when any post-screen escape, repeated-output mismatch, or
    protected-field mutation occurred. A zero failure-fixture count scores 0
    (no evidence, no credit).
    """

    security = metrics.get("security", {})
    preservation = metrics.get("preservation", {})
    if (
        (_as_number(security.get("post_screen_escapes")) or 0.0) > 0
        or (_as_number(security.get("repeated_output_mismatches")) or 0.0) > 0
        or (_as_number(preservation.get("protected_field_mutations")) or 0.0) > 0
    ):
        return 0.0
    agreement = security.get("expected_outcome_agreement", {})
    records = _as_number(agreement.get("records")) or 0.0
    matches = _as_number(agreement.get("matches")) or 0.0
    if records <= 0:
        return 0.0
    return 20.0 * (matches / records)


def _performance_axes(
    candidate_id: str,
    benchmarks: Mapping[str, dict[str, Any]],
    memory: Mapping[str, dict[str, Any]],
) -> dict[str, float | None]:
    bench = benchmarks.get(candidate_id, {})
    warm = bench.get("warm_latency_ms", {})
    medium = warm.get("medium", {}) if isinstance(warm, Mapping) else {}
    package_bytes = bench.get("package_bytes", {})
    model_bytes = bench.get("model_bytes", {})
    total_bytes: float | None = None
    package_total = _as_number(
        package_bytes.get("total_bytes") if isinstance(package_bytes, Mapping) else None
    )
    model_total = _as_number(
        model_bytes.get("total_bytes") if isinstance(model_bytes, Mapping) else None
    )
    if package_total is not None or model_total is not None:
        total_bytes = (package_total or 0.0) + (model_total or 0.0)
    cold = bench.get("cold_initialization", {})
    return {
        "warm_p95_medium_latency_ms": _as_number(
            medium.get("p95") if isinstance(medium, Mapping) else None
        ),
        "isolated_peak_bytes": _as_number(
            memory.get(candidate_id, {}).get("peak_bytes")
        ),
        "installed_package_model_bytes": total_bytes,
        "cold_initialization_median_seconds": _as_number(
            cold.get("median_seconds") if isinstance(cold, Mapping) else None
        ),
    }


def _performance_score(
    candidate_id: str,
    candidate_ids: Sequence[str],
    benchmarks: Mapping[str, dict[str, Any]],
    memory: Mapping[str, dict[str, Any]],
) -> float:
    """D4 = 10 * mean over four axes of ``min(1, best/candidate)``.

    Axes: warm p95 medium-payload latency, isolated peak memory, installed
    package+model bytes, cold-initialization median. ``best`` is the smallest
    strictly positive value across candidates; a candidate value of 0 scores
    a full 1.0 on that axis (nothing beats free); a missing measurement
    scores 0.0 (no evidence, no credit).
    """

    axes_by_candidate = {
        cid: _performance_axes(cid, benchmarks, memory) for cid in candidate_ids
    }
    ratios: list[float] = []
    for axis in axes_by_candidate[candidate_id]:
        positives = [
            value
            for value in (axes_by_candidate[cid][axis] for cid in candidate_ids)
            if value is not None and value > 0
        ]
        best = min(positives) if positives else None
        value = axes_by_candidate[candidate_id][axis]
        if value is None:
            ratios.append(0.0)
        elif value <= 0 or best is None:
            ratios.append(1.0)
        else:
            ratios.append(min(1.0, best / value))
    return 10.0 * _mean(ratios)


def _packaging_score(candidate_id: str) -> tuple[float, list[dict[str, Any]]]:
    """D5 = 10 minus the itemized ``PACKAGING_DEDUCTIONS`` (floored at 0)."""

    deductions = PACKAGING_DEDUCTIONS.get(candidate_id, [])
    total = sum(float(item["points"]) for item in deductions)
    return max(0.0, 10.0 - total), deductions


def _maintainability_score(candidate_id: str) -> tuple[float, str]:
    """D6: judged maintainability score from ``MAINTAINABILITY``."""

    entry = MAINTAINABILITY.get(
        candidate_id, {"score": 0.0, "reason": "unassessed candidate"}
    )
    return float(entry["score"]), str(entry["reason"])


def compute_weighted_scores(
    metrics_doc: Mapping[str, Any],
    hard_gates_doc: Mapping[str, Any],
    benchmarks_doc: Mapping[str, Any],
    memory_doc: Mapping[str, Any],
) -> dict[str, Any]:
    """Deterministic advisory weighted scores for every evaluated candidate.

    Consumes the aggregate artifact documents (``metrics.json``,
    ``hard-gates.json``, ``benchmark-results.json``, ``memory-isolated.json``)
    and returns ``{"schema_version": 1, "advisory": true, "score_basis":
    {...}, "candidates": [...sorted by candidate_id...]}`` with all six
    sub-scores, the total, the hard-gate ``aggregate_state``, and
    ``selection_eligible`` (true only when every hard gate passed).
    """

    metrics = _candidate_map(metrics_doc)
    gates = _candidate_map(hard_gates_doc)
    benchmarks = _candidate_map(benchmarks_doc)
    memory = _candidate_map(memory_doc)
    candidate_ids = sorted(metrics)

    candidates: list[dict[str, Any]] = []
    for candidate_id in candidate_ids:
        candidate_metrics = metrics[candidate_id]
        gate_entry = gates.get(candidate_id, {})
        gate_list = gate_entry.get("gates", [])
        aggregate_state, _passed, _pending, _failed = derive_gate_aggregate(
            gate_list if isinstance(gate_list, list) else []
        )
        d5, deductions = _packaging_score(candidate_id)
        d6, reason = _maintainability_score(candidate_id)
        scores = {
            "detection": round(_detection_score(candidate_metrics), 4),
            "precision_preservation": round(
                _precision_preservation_score(candidate_metrics), 4
            ),
            "security_failure": round(_security_score(candidate_metrics), 4),
            "performance_resource": round(
                _performance_score(candidate_id, candidate_ids, benchmarks, memory), 4
            ),
            "packaging_operational": round(d5, 4),
            "maintainability_seam": round(d6, 4),
        }
        candidates.append(
            {
                "candidate_id": candidate_id,
                "aggregate_state": aggregate_state,
                "selection_eligible": aggregate_state == "passed",
                "scores": scores,
                "total": round(sum(scores.values()), 4),
                "packaging_deductions": deductions,
                "maintainability_reason": reason,
            }
        )

    return {
        "schema_version": 1,
        "advisory": True,
        "score_basis": {
            "weights": dict(WEIGHTS),
            "formulas": {
                "detection": "30 * totals.f2 (0 when null)",
                "precision_preservation": (
                    "10 * totals.precision + 10 * mean(decision_preservation."
                    "pass_ratio, 1 - min(1, (destructive_false_positives + "
                    "clean_records_modified) / 10))"
                ),
                "security_failure": (
                    "20 * expected_outcome_agreement.matches/records; forced 0 "
                    "when post_screen_escapes > 0 or repeated_output_mismatches "
                    "> 0 or protected_field_mutations > 0"
                ),
                "performance_resource": (
                    "10 * mean over axes [warm p95 medium latency ms, isolated "
                    "peak bytes, package+model total bytes, cold init median "
                    "seconds] of min(1, best/candidate); best = smallest "
                    "positive value; zero-cost axis scores 1.0; missing "
                    "measurement scores 0.0"
                ),
                "packaging_operational": (
                    "10 minus the itemized PACKAGING_DEDUCTIONS entries "
                    "(floored at 0)"
                ),
                "maintainability_seam": (
                    "judged score from the MAINTAINABILITY table, reason stated"
                ),
            },
            "inputs": [
                "metrics.json",
                "hard-gates.json",
                "benchmark-results.json",
                "memory-isolated.json",
            ],
        },
        "candidates": candidates,
    }
