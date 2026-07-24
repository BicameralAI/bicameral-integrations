# SPDX-License-Identifier: MIT
"""Candidate-neutral evaluation runner for the ADR-0020 redaction spike.

Executes every corpus record through the same Bicameral-owned pipeline the
production wrapper (``adapter.core.redaction_receipt``) enforces:

    serialization guard -> identity screen -> metadata-key screen
    -> candidate detector -> deterministic replacement
    -> hard-screen postcondition

and emits one JSON-serializable candidate result document containing
per-record outcomes, determinism evidence, and the hard-gate results defined
by the evaluation contract (``_review-scratch/adr0020/design-corpus.md``).

Fail-closed enforcement and observation (issue #290)
----------------------------------------------------
Production semantics on any redaction failure are: no envelope is emitted, no
sink is called, and the ingestion cursor does not advance. That contract is
codified in ``runtime/cursor_policy.py`` ("Sensitive-data rejection is never
silently advanced"; schema/gate failure -> quarantine, not advance) and in
``adapter.core.redaction_receipt.guarded_sanitize_observation`` ("no envelope,
no sink call, no cursor advancement may follow" a typed
:class:`RedactionFailure`). The harness PROVES the same invariant by
observation, not modeling: every record outcome is routed through an
instrumented sink + cursor (``boundary.route_outcome``) and the gates check
the OBSERVED call counts (0/0 on failure, exactly 1/1 on success).

Candidate execution itself runs inside a per-candidate worker process
(``worker.CandidateWorkerManager``) that mirrors the production
``_WorkerManager`` deadline semantics, so ``per_record_budget_seconds`` is an
ENFORCED wall-clock deadline with hard termination — not an honor-system
number — and hang/crash/storm fault probes terminate the ACTUAL candidate's
worker, never a baseline stand-in.

Raw corpus values live only in memory while hard gates are computed; the
returned document carries digests, offsets, and counts only.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import importlib
import json
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from adapter.core.redaction import redact_with_findings
from adapter.core.redaction_receipt import _GATE_BUDGET_SECONDS
from adapter.core.sensitive import detect_sensitive

from .backends import create_backend
from .backends.faults import FaultInjectedBackend
from .boundary import RecordingCursor, RecordingSink, route_outcome
from .policy import LabelMap, RedactionPolicy, canonical_digest, configuration_digest
from .seam import BackendError, BackendFinding, BackendIdentity, RedactionBackend
from .worker import (
    CandidateWorkerManager,
    WorkerFailure,
    orphan_pids,
    psutil_available,
    python_child_pids,
)

SCHEMA_VERSION = 1

#: Faults whose only honest proof is a hard-terminated child process.
_SUBPROCESS_FAULTS = ("hang", "worker_crash")
_STORM_FAULT = "timeout_storm"
_INIT_FAULTS = ("invalid_configuration", "missing_model", "init_failure")
_STORM_CONCURRENCY = 8
_STORM_JOIN_TOLERANCE_SECONDS = 10.0
_ORPHAN_SETTLE_SECONDS = 3.0
#: Generous ceiling for out-of-deadline worker initialization (heavy models).
_PREWARM_TIMEOUT_SECONDS = 600.0
#: Deterministic timestamp for evaluation receipts (reproducible evidence).
_RECEIPT_COMPLETED_AT = "2026-01-01T00:00:00Z"
_PROBE_PAYLOAD_CLASSES = ("small", "medium", "large", "max_admitted")
#: Reasons that imply the manager hard-terminated (recycled) the worker.
_WORKER_KILL_REASONS = ("backend_timeout", "backend_crash")

_PATH_TOKEN_RE = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


class HarnessRejection(Exception):
    """Typed, value-free harness-side rejection (mirrors RedactionFailure)."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


# ---------------------------------------------------------------------------
# Field-path convention: "excerpt", "metadata.webhook.issue.body",
# "metadata.comments[0].body" — dotted keys, list index in brackets.
# ---------------------------------------------------------------------------


def _parse_path(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    for match in _PATH_TOKEN_RE.finditer(path):
        key, index = match.group(1), match.group(2)
        if key is not None:
            tokens.append(key)
        else:
            tokens.append(int(index))
    if not tokens:
        raise KeyError(path)
    return tokens


def resolve_path(root: Any, path: str) -> Any:
    """Resolve a dotted/bracketed field path; raises KeyError when absent."""

    node = root
    for token in _parse_path(path):
        if isinstance(token, int):
            if not isinstance(node, list) or token >= len(node):
                raise KeyError(path)
            node = node[token]
        else:
            if not isinstance(node, dict) or token not in node:
                raise KeyError(path)
            node = node[token]
    return node


def set_path(root: Any, path: str, value: Any) -> None:
    """Set a dotted/bracketed field path in-place; raises KeyError when absent."""

    tokens = _parse_path(path)
    node = root
    for token in tokens[:-1]:
        if isinstance(token, int):
            if not isinstance(node, list) or token >= len(node):
                raise KeyError(path)
            node = node[token]
        else:
            if not isinstance(node, dict) or token not in node:
                raise KeyError(path)
            node = node[token]
    last = tokens[-1]
    if isinstance(last, int):
        if not isinstance(node, list) or last >= len(node):
            raise KeyError(path)
        node[last] = value
    else:
        if not isinstance(node, dict):
            raise KeyError(path)
        node[last] = value


def iter_string_leaves(tree: Any, prefix: str) -> list[tuple[str, str]]:
    """Every string leaf under ``tree`` as ``(field_path, value)`` pairs."""

    leaves: list[tuple[str, str]] = []
    if isinstance(tree, str):
        leaves.append((prefix, tree))
    elif isinstance(tree, dict):
        for key in tree:
            leaves.extend(iter_string_leaves(tree[key], f"{prefix}.{key}"))
    elif isinstance(tree, (list, tuple)):
        for index, item in enumerate(tree):
            leaves.extend(iter_string_leaves(item, f"{prefix}[{index}]"))
    return leaves


# ---------------------------------------------------------------------------
# Serialization guard (mirror of adapter.core.redaction_receipt._canonical)
# ---------------------------------------------------------------------------


def _canonical_guard(value: Any) -> Any:
    if isinstance(value, bytes):
        raise HarnessRejection("unsupported_binary")
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _canonical_guard(sub)
            for key, sub in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_guard(item) for item in value]
    raise HarnessRejection("unsupported_payload")


def _serialization_guard(observation: dict[str, Any], policy: RedactionPolicy) -> None:
    canonical = _canonical_guard(observation)
    try:
        serialized = json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
    except (TypeError, ValueError):
        raise HarnessRejection("unsupported_payload") from None
    try:
        encoded = serialized.encode("utf-8")
    except UnicodeEncodeError:
        raise HarnessRejection("unsupported_payload") from None
    if len(encoded) > policy.max_payload_bytes:
        raise HarnessRejection("oversized_payload")


def _sha256_text(value: str) -> str:
    """JSON-canonical value digest, matching the merged evaluation contract
    validator (`scripts/validate_redaction_evaluation_contract.py`)."""

    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _identity_screen(
    observation: dict[str, Any], policy: RedactionPolicy
) -> dict[str, str]:
    """Screen identity fields; return their value digests (value-free)."""

    digests: dict[str, str] = {}
    for field_path in policy.identity_fields:
        try:
            value = resolve_path(observation, field_path)
        except KeyError:
            continue
        if not isinstance(value, str) or value == "":
            continue
        if detect_sensitive(value):
            raise HarnessRejection("sensitive_identity_field")
        digests[field_path] = _sha256_text(value)
    return digests


def _metadata_key_screen(observation: dict[str, Any], policy: RedactionPolicy) -> None:
    """Wrapper-owned recursive key screen, identical for every candidate."""

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, sub in node.items():
                key_text = str(key)
                redacted_key, key_findings = redact_with_findings(key_text)
                if redacted_key != key_text or any(key_findings.values()):
                    raise HarnessRejection("sensitive_metadata_key")
                _walk(sub)
        elif isinstance(node, (list, tuple)):
            for item in node:
                _walk(item)

    for tree_field in policy.admitted_tree_fields:
        _walk(observation.get(tree_field))


# ---------------------------------------------------------------------------
# Findings: validation, deterministic overlap resolution, replacement
# ---------------------------------------------------------------------------


def validate_findings(findings: Sequence[BackendFinding], text: str) -> None:
    """Reject non-integer or out-of-range spans (``malformed_backend_findings``)."""

    for finding in findings:
        start, end = finding.start, finding.end
        if isinstance(start, bool) or isinstance(end, bool):
            raise HarnessRejection("malformed_backend_findings")
        if not isinstance(start, int) or not isinstance(end, int):
            raise HarnessRejection("malformed_backend_findings")
        if not (0 <= start < end <= len(text)):
            raise HarnessRejection("malformed_backend_findings")


def resolve_overlaps(findings: Sequence[BackendFinding]) -> list[BackendFinding]:
    """Deterministic overlap resolution: sort by (start, -length, subtype),
    greedily skip anything overlapping an already-accepted span."""

    ordered = sorted(
        findings, key=lambda f: (f.start, -(f.end - f.start), f.subtype)
    )
    taken: list[tuple[int, int]] = []
    resolved: list[BackendFinding] = []
    for finding in ordered:
        if any(
            finding.start < t_end and finding.end > t_start
            for t_start, t_end in taken
        ):
            continue
        taken.append((finding.start, finding.end))
        resolved.append(finding)
    return resolved


def apply_replacements(
    text: str, findings: Sequence[BackendFinding], policy: RedactionPolicy
) -> str:
    """Replace resolved spans right-to-left so earlier offsets stay valid."""

    out = text
    for finding in sorted(findings, key=lambda f: f.start, reverse=True):
        out = out[: finding.start] + policy.replacement(finding.subtype) + out[finding.end :]
    return out


def _finding_doc(finding: BackendFinding, field_path: str) -> dict[str, Any]:
    return {
        "category": finding.category,
        "subtype": finding.subtype,
        "field_path": field_path,
        "start": finding.start,
        "end": finding.end,
        "backend_label": finding.backend_label,
        "confidence": finding.confidence,
    }


# ---------------------------------------------------------------------------
# Single deterministic pipeline execution
# ---------------------------------------------------------------------------


@dataclass
class Execution:
    """One value-bearing pipeline pass (values stay in memory only)."""

    outcome: str
    failure_reason: str | None = None
    findings: list[dict[str, Any]] = field(default_factory=list)
    sanitized_fields: dict[str, str] = field(default_factory=dict)
    original_fields: dict[str, str] = field(default_factory=dict)
    identity_digests: dict[str, str] = field(default_factory=dict)
    post_screen_hits: int = 0
    structural_mirror_ok: bool = True

    def digest(self) -> str:
        return canonical_digest(
            {"fields": self.sanitized_fields, "findings": self.findings}
        )


def _admitted_fields(
    observation: dict[str, Any], policy: RedactionPolicy
) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    for name in policy.admitted_text_fields:
        if name in observation and isinstance(observation[name], str):
            fields.append((name, observation[name]))
    for tree_field in policy.admitted_tree_fields:
        tree = observation.get(tree_field)
        if tree is not None:
            fields.extend(iter_string_leaves(tree, tree_field))
    return fields


def execute_once(
    observation: dict[str, Any],
    backend: RedactionBackend,
    policy: RedactionPolicy,
) -> Execution:
    """Run the full candidate-neutral pipeline once over one observation."""

    try:
        _serialization_guard(observation, policy)
        identity_digests = _identity_screen(observation, policy)
        _metadata_key_screen(observation, policy)
    except HarnessRejection as rejection:
        return Execution(outcome="failed_closed", failure_reason=rejection.reason)

    findings_docs: list[dict[str, Any]] = []
    sanitized_fields: dict[str, str] = {}
    original_fields: dict[str, str] = {}
    for field_path, text in _admitted_fields(observation, policy):
        original_fields[field_path] = text
        try:
            raw_findings = backend.analyze(text, field_path=field_path, policy=policy)
        except BackendError as err:
            return Execution(
                outcome="failed_closed",
                failure_reason=err.reason,
                identity_digests=identity_digests,
            )
        except Exception:
            return Execution(
                outcome="failed_closed",
                failure_reason="backend_crash",
                identity_digests=identity_digests,
            )
        try:
            validate_findings(raw_findings, text)
        except HarnessRejection as rejection:
            return Execution(
                outcome="failed_closed",
                failure_reason=rejection.reason,
                identity_digests=identity_digests,
            )
        resolved = resolve_overlaps(raw_findings)
        sanitized_fields[field_path] = apply_replacements(text, resolved, policy)
        findings_docs.extend(_finding_doc(f, field_path) for f in resolved)

    # Hard-screen postcondition: the un-bypassable backstop. An escape is a
    # clean failed-closed outcome (production would reject the emission), not
    # an exception path.
    post_screen_hits = sum(
        len(detect_sensitive(text)) for text in sanitized_fields.values()
    )
    if post_screen_hits > 0:
        return Execution(
            outcome="failed_closed",
            failure_reason="post_screen_escape",
            identity_digests=identity_digests,
            post_screen_hits=post_screen_hits,
        )

    unchanged = not findings_docs and all(
        sanitized_fields[path] == original_fields[path] for path in sanitized_fields
    )
    execution = Execution(
        outcome="unchanged" if unchanged else "sanitized",
        findings=findings_docs,
        sanitized_fields=sanitized_fields,
        original_fields=original_fields,
        identity_digests=identity_digests,
        post_screen_hits=0,
    )
    try:
        json.dumps(_build_sanitized_observation(observation, sanitized_fields))
    except (TypeError, ValueError, HarnessRejection, KeyError):
        execution.structural_mirror_ok = False
    return execution


def _build_sanitized_observation(
    observation: dict[str, Any], sanitized_fields: dict[str, str]
) -> dict[str, Any]:
    sanitized = copy.deepcopy(observation)
    for field_path, text in sanitized_fields.items():
        set_path(sanitized, field_path, text)
    return sanitized


# ---------------------------------------------------------------------------
# Worker-side pure pipeline entry (executed INSIDE the candidate worker)
# ---------------------------------------------------------------------------


def execute_record_in_worker(
    backend: RedactionBackend,
    observation: dict[str, Any],
    policy: RedactionPolicy,
    directives: dict[str, Any],
) -> dict[str, Any]:
    """Run the ENTIRE per-record pipeline once; return a picklable result doc.

    Pure function used as the child-process pipeline body by
    ``worker._candidate_worker_loop`` (no corpus-loader dependency). Semantics
    are exactly the historical in-process pipeline: serialization guard,
    oversized/binary rejection, identity screen, metadata-key screen, analyze,
    finding validation, deterministic overlap resolution, right-to-left
    replacement, hard-screen postcondition. The returned document carries the
    value-bearing sanitized field map and sanitized observation; the PARENT
    strips sanitized text before persisting, keeping digests only.
    Fault directives (hang/worker_crash) are applied by the worker loop before
    this function runs.
    """

    del directives
    execution = execute_once(observation, backend, policy)
    doc: dict[str, Any] = {
        "outcome": execution.outcome,
        "failure_reason": execution.failure_reason,
        "findings": execution.findings,
        "sanitized_fields": dict(execution.sanitized_fields),
        "identity_digests": dict(execution.identity_digests),
        "post_screen_hits": execution.post_screen_hits,
        "structural_mirror_ok": execution.structural_mirror_ok,
        "execution_digest": execution.digest(),
    }
    if execution.outcome in ("sanitized", "unchanged"):
        try:
            doc["sanitized_observation"] = _build_sanitized_observation(
                observation, execution.sanitized_fields
            )
        except KeyError:
            doc["structural_mirror_ok"] = False
            doc["sanitized_observation"] = None
    return doc


def _healthy_probe_observation(record_id: str, excerpt: str) -> dict[str, Any]:
    """Synthetic, sensitive-free observation for recovery/deadline probes."""

    return {
        "source_ref": {
            "source_id": f"{record_id}-source",
            "ref": f"{record_id}-ref",
            "url": "",
            "kind": "synthetic",
        },
        "excerpt": excerpt,
        "title": record_id,
        "author": "harness",
        "mode": "batch",
        "timestamp": "2026-01-01T00:00:00Z",
        "provider_event_id": f"{record_id}-event",
        "provider_resource_id": f"{record_id}-resource",
        "evidence_id": f"{record_id}-evidence",
        "evidence_metadata": {},
        "metadata": {},
    }


# ---------------------------------------------------------------------------
# Fault probes against the ACTUAL candidate's worker (issue #290 defect 2)
# ---------------------------------------------------------------------------


def run_worker_timeout_storm(
    observation: dict[str, Any],
    policy: RedactionPolicy,
    budget: float,
    manager: CandidateWorkerManager,
    *,
    concurrency: int = _STORM_CONCURRENCY,
    prewarm_timeout_seconds: float = _PREWARM_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Concurrent hang calls against the ONE candidate worker manager.

    Every caller uses its OWN per-caller deadline (lock wait included), so all
    must fail ``backend_timeout``; afterwards the orphan check runs for this
    candidate, then one healthy record through the SAME manager proves
    recovery. Prewarm times spent restoring the worker are recorded honestly
    and never blended into any caller's budget.
    """

    psutil_ok = psutil_available()
    before = python_child_pids()
    pids_before = set(manager.pids_seen())
    prewarm_before_seconds = manager.prewarm(prewarm_timeout_seconds)
    storm_pids: set[int] = set()
    pid_at_start = manager.worker_pid()
    if pid_at_start is not None:
        storm_pids.add(pid_at_start)

    reasons: list[str | None] = [None] * concurrency

    def _one(slot: int) -> None:
        try:
            manager.call(observation, policy, {"fault": "hang"}, budget)
        except WorkerFailure as failure:
            reasons[slot] = failure.reason
        else:
            reasons[slot] = "no_failure"

    threads = [
        threading.Thread(target=_one, args=(slot,), daemon=True)
        for slot in range(concurrency)
    ]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    deadline = started + budget + _STORM_JOIN_TOLERANCE_SECONDS
    for thread in threads:
        thread.join(max(0.0, deadline - time.monotonic()))
    finished = all(not thread.is_alive() for thread in threads)
    all_timed_out = finished and all(
        reason == "backend_timeout" for reason in reasons
    )

    orphans: int | None = None
    if psutil_ok:
        settle_deadline = time.monotonic() + _ORPHAN_SETTLE_SECONDS
        leftover = orphan_pids(before)
        while leftover and time.monotonic() < settle_deadline:
            time.sleep(0.1)
            leftover = orphan_pids(before)
        orphans = len(leftover)

    recovery_prewarm_seconds = manager.prewarm(prewarm_timeout_seconds)
    healthy = _healthy_probe_observation(
        "storm-recovery", "storm recovery probe with no sensitive content"
    )
    try:
        recovery_doc = manager.call(
            healthy, policy, {}, policy.per_record_budget_seconds
        )
    except WorkerFailure:
        recovered = False
    else:
        recovered = recovery_doc.get("outcome") in ("sanitized", "unchanged")
    return {
        "storm_concurrency": concurrency,
        "all_timed_out": all_timed_out,
        # Bounded cleanup is observable as every caller returning inside the
        # bounded join window (deadline + documented cleanup tolerance).
        "cleanup_ok": finished,
        "orphans": orphans if orphans is not None else -1,
        "recovered": recovered,
        "candidate_id": manager.candidate_id,
        "configuration_digest": manager.configuration_digest,
        "worker_pids": sorted(
            storm_pids | (set(manager.pids_seen()) - pids_before)
        ),
        "prewarm_before_seconds": prewarm_before_seconds,
        "recovery_prewarm_seconds": recovery_prewarm_seconds,
    }


def run_production_deadline_probes(
    manager: CandidateWorkerManager,
    policy: RedactionPolicy,
    *,
    prewarm_timeout_seconds: float = _PREWARM_TIMEOUT_SECONDS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Hard per-candidate evidence against the PRODUCTION gate budget.

    Runs the benchmark payload classes (small/medium/large/max_admitted) as
    synthetic observations through the candidate worker with
    ``budget_seconds=_GATE_BUDGET_SECONDS`` (imported from
    ``adapter.core.redaction_receipt`` — the production 5.0 s gate budget).
    Between warm probes the worker is re-prewarmed (recorded) if a previous
    probe killed it. One explicit ``cold_worker`` probe shuts the worker down
    first so initialization falls INSIDE the production budget, matching
    production lazy-spawn semantics. Enforced terminations are recorded per
    probe; these measurements are hard evidence, never benchmark reuse.

    Returns ``(probes, prewarm_events)``.
    """

    from .bench import _observation_document, build_payloads

    payloads = build_payloads(policy)
    probes: list[dict[str, Any]] = []
    prewarm_events: list[dict[str, Any]] = []

    def _probe(payload_class: str, text: str, probe_kind: str) -> dict[str, Any]:
        observation = _observation_document(text)
        started = time.perf_counter()
        enforced = False
        cleanup: dict[str, Any] | None = None
        try:
            doc = manager.call(observation, policy, {}, _GATE_BUDGET_SECONDS)
        except WorkerFailure as failure:
            outcome = failure.reason
            enforced = failure.reason in _WORKER_KILL_REASONS
            cleanup = dict(manager.last_cleanup)
        else:
            if doc.get("outcome") == "failed_closed":
                outcome = f"failed_closed:{doc.get('failure_reason')}"
            else:
                outcome = str(doc.get("outcome"))
        return {
            "payload_class": payload_class,
            "probe": probe_kind,
            "budget_seconds": _GATE_BUDGET_SECONDS,
            "outcome": outcome,
            "duration_ms": (time.perf_counter() - started) * 1000.0,
            "enforced_termination": enforced,
            "cleanup": cleanup,
        }

    for payload_class in _PROBE_PAYLOAD_CLASSES:
        if not manager.worker_alive():
            seconds = manager.prewarm(prewarm_timeout_seconds)
            prewarm_events.append(
                {
                    "phase": f"deadline-probe:{payload_class}",
                    "seconds": seconds,
                    "worker_pid": manager.worker_pid(),
                }
            )
        probes.append(_probe(payload_class, payloads[payload_class], "warm"))

    # Cold-worker probe: initialization INSIDE the production budget.
    manager.shutdown()
    probes.append(_probe("small", payloads["small"], "cold_worker"))
    return probes, prewarm_events


# ---------------------------------------------------------------------------
# Per-record processing (dispatches normal records and every fault class)
# ---------------------------------------------------------------------------


@dataclass
class ProcessOutcome:
    """Per-record harness output plus in-memory-only value-bearing context."""

    result: dict[str, Any]
    sanitized_fields: dict[str, str] = field(default_factory=dict)
    sanitized_observation: dict[str, Any] | None = None
    #: Latest cumulative unmapped-label snapshot: {"worker_pid", "labels"}.
    unmapped_snapshot: dict[str, Any] | None = None


def _failure_result(
    base: dict[str, Any],
    reason: str,
    *,
    identity_digests: dict[str, str] | None = None,
    post_screen_hits: int = 0,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = dict(base)
    result.update(
        {
            "outcome": "failed_closed",
            "failure_reason": reason,
            "post_screen_hits": post_screen_hits,
            "repeat_digests": [],
        }
    )
    if identity_digests:
        result["identity_digests"] = identity_digests
    if extra:
        result.update(extra)
    return result


def process_record(
    input_record: dict[str, Any],
    *,
    backend: RedactionBackend,
    policy: RedactionPolicy,
    classes: Sequence[str] = (),
    determinism_repeats: int = 1,
    fault_budget_seconds: float = 2.0,
    manager: CandidateWorkerManager | None = None,
) -> ProcessOutcome:
    """Execute one corpus input record end-to-end (all fault classes included).

    With a ``manager``, normal candidate execution (and every determinism
    repeat) runs inside the candidate worker under the ENFORCED
    ``policy.per_record_budget_seconds`` deadline; hang/worker_crash/storm
    faults terminate the actual candidate's worker. Without a manager (unit
    tests with composed fake backends) execution stays in-process and no
    subprocess fault probes are available.
    """

    record_id = str(input_record.get("record_id", ""))
    source_shape = str(input_record.get("source_shape", ""))
    base = {
        "record_id": record_id,
        "source_shape": source_shape,
        "classes": sorted(classes),
    }
    directives = input_record.get("eval_directives") or {}
    fault = directives.get("fault")
    observation = copy.deepcopy(input_record.get("observation") or {})

    binary = directives.get("binary_field")
    if binary:
        set_path(observation, binary["path"], base64.b64decode(binary["base64"]))

    started = time.perf_counter()

    if fault:
        result = _run_fault_record(
            fault, base, observation, backend, policy, fault_budget_seconds, manager
        )
        result["duration_ms"] = (time.perf_counter() - started) * 1000.0
        result["fault"] = fault
        return ProcessOutcome(result=result)

    if manager is not None:
        return _process_record_via_worker(
            base,
            observation,
            policy,
            manager,
            determinism_repeats=determinism_repeats,
            started=started,
        )

    execution = execute_once(observation, backend, policy)
    duration_ms = (time.perf_counter() - started) * 1000.0

    if execution.outcome == "failed_closed":
        reason = execution.failure_reason or "unknown_failure"
        result = _failure_result(
            base,
            reason,
            identity_digests=execution.identity_digests,
            post_screen_hits=execution.post_screen_hits,
        )
        result["duration_ms"] = duration_ms
        return ProcessOutcome(result=result)

    digests = [execution.digest()]
    for _ in range(max(0, determinism_repeats - 1)):
        repeat = execute_once(observation, backend, policy)
        digests.append(repeat.digest())

    result = dict(base)
    result.update(
        {
            "outcome": execution.outcome,
            "failure_reason": None,
            "findings": execution.findings,
            "field_digests": {
                path: _sha256_text(text)
                for path, text in sorted(execution.sanitized_fields.items())
            },
            "identity_digests": execution.identity_digests,
            "post_screen_hits": 0,
            "duration_ms": duration_ms,
            "repeat_digests": digests,
            "structural_mirror_ok": execution.structural_mirror_ok,
        }
    )
    return ProcessOutcome(
        result=result,
        sanitized_fields=execution.sanitized_fields,
        sanitized_observation=_build_sanitized_observation(
            observation, execution.sanitized_fields
        ),
    )


def _process_record_via_worker(
    base: dict[str, Any],
    observation: dict[str, Any],
    policy: RedactionPolicy,
    manager: CandidateWorkerManager,
    *,
    determinism_repeats: int,
    started: float,
) -> ProcessOutcome:
    """Normal-record path through the candidate worker (enforced deadline)."""

    budget = policy.per_record_budget_seconds
    try:
        doc = manager.call(observation, policy, {}, budget)
    except WorkerFailure as failure:
        duration_ms = (time.perf_counter() - started) * 1000.0
        extra: dict[str, Any] = {}
        if failure.reason in _WORKER_KILL_REASONS:
            extra["cleanup"] = dict(manager.last_cleanup)
        result = _failure_result(base, failure.reason, extra=extra or None)
        result["duration_ms"] = duration_ms
        return ProcessOutcome(result=result)
    duration_ms = (time.perf_counter() - started) * 1000.0
    snapshot = _unmapped_snapshot(doc)

    if doc.get("outcome") == "failed_closed":
        result = _failure_result(
            base,
            str(doc.get("failure_reason") or "unknown_failure"),
            identity_digests=dict(doc.get("identity_digests") or {}),
            post_screen_hits=int(doc.get("post_screen_hits") or 0),
        )
        result["duration_ms"] = duration_ms
        return ProcessOutcome(result=result, unmapped_snapshot=snapshot)

    digests = [str(doc.get("execution_digest"))]
    for _ in range(max(0, determinism_repeats - 1)):
        try:
            repeat_doc = manager.call(observation, policy, {}, budget)
        except WorkerFailure as failure:
            digests.append(f"repeat_failed:{failure.reason}")
            continue
        if repeat_doc.get("outcome") == "failed_closed":
            digests.append(f"repeat_failed:{repeat_doc.get('failure_reason')}")
        else:
            digests.append(str(repeat_doc.get("execution_digest")))
            snapshot = _unmapped_snapshot(repeat_doc) or snapshot

    sanitized_fields = {
        str(path): str(text)
        for path, text in (doc.get("sanitized_fields") or {}).items()
    }
    result = dict(base)
    result.update(
        {
            "outcome": str(doc.get("outcome")),
            "failure_reason": None,
            "findings": list(doc.get("findings") or []),
            "field_digests": {
                path: _sha256_text(text)
                for path, text in sorted(sanitized_fields.items())
            },
            "identity_digests": dict(doc.get("identity_digests") or {}),
            "post_screen_hits": 0,
            "duration_ms": duration_ms,
            "repeat_digests": digests,
            "structural_mirror_ok": bool(doc.get("structural_mirror_ok")),
            "worker_pid": doc.get("worker_pid"),
        }
    )
    sanitized_observation = doc.get("sanitized_observation")
    return ProcessOutcome(
        result=result,
        sanitized_fields=sanitized_fields,
        sanitized_observation=(
            sanitized_observation
            if isinstance(sanitized_observation, dict)
            else None
        ),
        unmapped_snapshot=snapshot,
    )


def _unmapped_snapshot(doc: dict[str, Any]) -> dict[str, Any] | None:
    labels = doc.get("unmapped_labels")
    pid = doc.get("worker_pid")
    if not isinstance(labels, dict) or not isinstance(pid, int):
        return None
    return {"worker_pid": pid, "labels": dict(labels)}


def _run_fault_record(
    fault: str,
    base: dict[str, Any],
    observation: dict[str, Any],
    backend: RedactionBackend,
    policy: RedactionPolicy,
    fault_budget_seconds: float,
    manager: CandidateWorkerManager | None,
) -> dict[str, Any]:
    probe_text = str(observation.get("excerpt", ""))

    if fault in _SUBPROCESS_FAULTS:
        # Hang/crash probes terminate the ACTUAL candidate's worker: the
        # directive travels to the candidate worker, which sleeps past the
        # deadline (hang) or dies abruptly (worker_crash). Never a baseline
        # stand-in (issue #290 defect 2).
        if manager is None:
            raise ValueError(
                "subprocess fault records require a CandidateWorkerManager"
            )
        try:
            manager.call(observation, policy, {"fault": fault}, fault_budget_seconds)
        except WorkerFailure as failure:
            reason = failure.reason
        else:
            reason = "fault_did_not_fire"
        return _failure_result(
            base, reason, extra={"cleanup": dict(manager.last_cleanup)}
        )

    if fault == _STORM_FAULT:
        if manager is None:
            raise ValueError(
                "timeout-storm records require a CandidateWorkerManager"
            )
        storm = run_worker_timeout_storm(
            observation, policy, fault_budget_seconds, manager
        )
        reason = "backend_timeout" if storm["all_timed_out"] else "storm_incomplete"
        return _failure_result(base, reason, extra={"storm": storm})

    fault_backend = FaultInjectedBackend(backend.identity, fault)

    if fault in _INIT_FAULTS:
        # Init-class faults stay parent-side by design: they prove typed
        # initialization failure handling and never reach a worker.
        try:
            fault_backend.initialize()
        except BackendError as err:
            return _failure_result(base, err.reason)
        except Exception:
            return _failure_result(base, "backend_crash")
        return _failure_result(base, "fault_did_not_fire")

    scope = {"probe_scope": "finding_validation"}

    if fault == "nondeterministic":
        first = fault_backend.analyze(probe_text, field_path="excerpt", policy=policy)
        second = fault_backend.analyze(probe_text, field_path="excerpt", policy=policy)
        if first != second:
            return _failure_result(
                base, "nondeterministic_backend_output", extra=scope
            )
        return _failure_result(base, "fault_did_not_fire", extra=scope)

    # In-process validation faults (exception, malformed spans): they test the
    # harness's finding-validation path, not process isolation, so they run
    # the normal pipeline with the fault backend in-process; the recorded
    # probe_scope makes that scope explicit.
    execution = execute_once(observation, fault_backend, policy)
    if execution.outcome == "failed_closed":
        return _failure_result(
            base,
            execution.failure_reason or "unknown_failure",
            identity_digests=execution.identity_digests,
            post_screen_hits=execution.post_screen_hits,
            extra=scope,
        )
    return _failure_result(base, "fault_did_not_fire", extra=scope)


# ---------------------------------------------------------------------------
# Corpus access (the loader is generated by a sibling task; import lazily)
# ---------------------------------------------------------------------------


def _corpus_loader() -> Any:
    return importlib.import_module("tests.redaction_evaluation.corpus_loader")


def corpus_digest_from_manifest(manifest_records: Sequence[dict[str, Any]]) -> str:
    """sha256 over the sorted record ``input_sha256`` values, concatenated."""

    concatenated = "".join(
        sorted(str(record["input_sha256"]) for record in manifest_records)
    )
    return "sha256:" + hashlib.sha256(concatenated.encode("utf-8")).hexdigest()


def _load_expected(repo_root: Path, expected_path: str) -> dict[str, Any]:
    with (repo_root / expected_path).open("r", encoding="utf-8") as handle:
        data: dict[str, Any] = json.load(handle)
    return data


# ---------------------------------------------------------------------------
# Hard gates
# ---------------------------------------------------------------------------


def _gate(
    gate_id: str,
    status: str,
    *,
    affected: Iterable[str] = (),
    evidence: Any = None,
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": status,
        "affected_record_ids": sorted(affected),
        "evidence": evidence,
        "raw_values_included": False,
    }


def _fault_of(record_result: dict[str, Any]) -> str | None:
    fault = record_result.get("fault")
    return str(fault) if fault else None


def _fail_closed_gate(
    gate_id: str,
    records: list[dict[str, Any]],
    faults: tuple[str, ...],
    expected_reasons: dict[str, str],
    *,
    extra_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    relevant = [r for r in records if _fault_of(r) in faults]
    if not relevant:
        return _gate(gate_id, "pending", evidence="no_records_in_corpus")
    affected = [
        r["record_id"]
        for r in relevant
        if r.get("outcome") != "failed_closed"
        or r.get("failure_reason") != expected_reasons[_fault_of(r) or ""]
    ]
    evidence: dict[str, Any] = {"records_checked": len(relevant)}
    if extra_evidence:
        evidence.update(extra_evidence)
    return _gate(
        gate_id,
        "failed" if affected else "passed",
        affected=affected,
        evidence=evidence,
    )


def _fault_worker_pids(
    records: list[dict[str, Any]], faults: tuple[str, ...]
) -> list[int]:
    """Worker pids recorded by this candidate's own fault probes."""

    pids: set[int] = set()
    for record in records:
        if _fault_of(record) not in faults:
            continue
        cleanup = record.get("cleanup") or {}
        pid = cleanup.get("pid")
        if isinstance(pid, int):
            pids.add(pid)
        storm = record.get("storm") or {}
        for storm_pid in storm.get("worker_pids", []):
            if isinstance(storm_pid, int):
                pids.add(storm_pid)
    return sorted(pids)


@dataclass
class _GateContext:
    """In-memory-only value-bearing context needed to compute hard gates."""

    record_results: list[dict[str, Any]]
    sanitized_by_record: dict[str, dict[str, str]]
    sanitized_observations: dict[str, dict[str, Any]]
    input_observations: dict[str, dict[str, Any]]
    expected_by_record: dict[str, dict[str, Any]]
    determinism_mismatches: list[str]
    identity: BackendIdentity
    config_digest: str
    policy: RedactionPolicy
    #: Value-free execution evidence (prewarms, worker pids, deadline probes).
    execution_doc: dict[str, Any] = field(default_factory=dict)


def _raw_expected_values(context: _GateContext) -> dict[str, list[str]]:
    """Raw expected-span values per record, extracted from de-obfuscated input.

    The values exist only for the duration of the gate check; only counts and
    record ids leave this function's callers.
    """

    values: dict[str, list[str]] = {}
    for record_id, expected in context.expected_by_record.items():
        observation = context.input_observations.get(record_id)
        if observation is None:
            continue
        extracted: list[str] = []
        for entity in expected.get("expected_entities", []):
            try:
                text = resolve_path(observation, entity["field_path"])
            except KeyError:
                continue
            if isinstance(text, str):
                raw = text[entity["start"] : entity["end"]]
                if raw:
                    extracted.append(raw)
        if extracted:
            values[record_id] = extracted
    return values


def _gate_no_raw_leakage(
    context: _GateContext, document_without_gates: dict[str, Any]
) -> dict[str, Any]:
    serialized = json.dumps(document_without_gates, ensure_ascii=False)
    affected: list[str] = []
    checked = 0
    for record_id, raw_values in _raw_expected_values(context).items():
        for raw in raw_values:
            checked += 1
            if raw in serialized:
                affected.append(record_id)
                break
    return _gate(
        "no-raw-leakage",
        "failed" if affected else "passed",
        affected=affected,
        evidence={"raw_values_checked": checked},
    )


def _gate_mandatory_protection(context: _GateContext) -> dict[str, Any]:
    affected: list[str] = []
    checked = 0
    for record_id, expected in context.expected_by_record.items():
        observation = context.input_observations.get(record_id)
        result = next(
            (r for r in context.record_results if r["record_id"] == record_id), None
        )
        if observation is None or result is None:
            continue
        for entity in expected.get("expected_entities", []):
            if not entity.get("mandatory"):
                continue
            checked += 1
            if result.get("outcome") == "failed_closed":
                continue  # fail-closed protects the value by construction
            try:
                text = resolve_path(observation, entity["field_path"])
            except KeyError:
                continue
            if not isinstance(text, str):
                continue
            raw = text[entity["start"] : entity["end"]]
            sanitized = context.sanitized_by_record.get(record_id, {}).get(
                entity["field_path"]
            )
            if raw and sanitized is not None and raw in sanitized:
                affected.append(record_id)
    if checked == 0:
        return _gate(
            "mandatory-secret-protection", "pending", evidence="no_records_in_corpus"
        )
    return _gate(
        "mandatory-secret-protection",
        "failed" if affected else "passed",
        affected=affected,
        evidence={"mandatory_entities_checked": checked},
    )


def _gate_identity_preservation(context: _GateContext) -> dict[str, Any]:
    affected: list[str] = []
    for result in context.record_results:
        record_id = result["record_id"]
        observation = context.input_observations.get(record_id)
        expected = context.expected_by_record.get(record_id, {})
        if result.get("failure_reason") == "sensitive_identity_field":
            if expected.get("expected_failure_reason") != "sensitive_identity_field":
                affected.append(record_id)
            continue
        digests = result.get("identity_digests")
        if observation is None or not digests:
            continue
        for field_path, digest in digests.items():
            try:
                value = resolve_path(observation, field_path)
            except KeyError:
                affected.append(record_id)
                break
            if not isinstance(value, str) or _sha256_text(value) != digest:
                affected.append(record_id)
                break
        sanitized_observation = context.sanitized_observations.get(record_id)
        if sanitized_observation is not None:
            for field_path in digests:
                try:
                    sanitized_value = resolve_path(sanitized_observation, field_path)
                except KeyError:
                    affected.append(record_id)
                    break
                if _sha256_text(str(sanitized_value)) != digests[field_path]:
                    affected.append(record_id)
                    break
    return _gate(
        "identity-preservation",
        "failed" if affected else "passed",
        affected=set(affected),
        evidence={"records_checked": len(context.record_results)},
    )


def _gate_no_envelope_on_failure(context: _GateContext) -> dict[str, Any]:
    """OBSERVED boundary calls: 0/0 on failure, exactly 1/1 on success.

    ``observed_sink_calls``/``observed_cursor_advances`` come from routing
    every record result through the instrumented sink + cursor
    (``boundary.route_outcome``), so this gate reflects real calls, not
    modeled booleans (issue #290 defect 4).
    """

    affected: list[str] = []
    failed_count = 0
    success_count = 0
    for record in context.record_results:
        outcome = record.get("outcome")
        sink_calls = record.get("observed_sink_calls")
        advances = record.get("observed_cursor_advances")
        if outcome == "failed_closed":
            failed_count += 1
            if (
                sink_calls != 0
                or advances != 0
                or "field_digests" in record
                or "findings" in record
            ):
                affected.append(record["record_id"])
        elif outcome in ("sanitized", "unchanged"):
            success_count += 1
            if sink_calls != 1 or advances != 1:
                affected.append(record["record_id"])
    return _gate(
        "no-envelope-no-cursor-on-failure",
        "failed" if affected else "passed",
        affected=affected,
        evidence={
            "failed_closed_records": failed_count,
            "success_records_checked": success_count,
            "basis": "observed sink/cursor boundary calls per record",
        },
    )


def _gate_deterministic(context: _GateContext) -> dict[str, Any]:
    affected = list(context.determinism_mismatches)
    for result in context.record_results:
        if _fault_of(result) == "nondeterministic" and (
            result.get("failure_reason") != "nondeterministic_backend_output"
        ):
            affected.append(result["record_id"])
    return _gate(
        "deterministic-output",
        "failed" if affected else "passed",
        affected=affected,
        evidence={"mismatched_records": len(context.determinism_mismatches)},
    )


def _gate_bounded_cleanup(context: _GateContext) -> dict[str, Any]:
    storms = [r for r in context.record_results if _fault_of(r) == _STORM_FAULT]
    if not storms:
        return _gate(
            "bounded-cleanup-no-orphans", "pending", evidence="no_records_in_corpus"
        )
    affected = []
    storm_docs = []
    for result in storms:
        storm = result.get("storm", {})
        storm_docs.append(storm)
        if (
            storm.get("orphans") != 0
            or not storm.get("all_timed_out")
            or not storm.get("recovered")
            or not storm.get("cleanup_ok")
        ):
            affected.append(result["record_id"])
    return _gate(
        "bounded-cleanup-no-orphans",
        "failed" if affected else "passed",
        affected=affected,
        evidence={
            "candidate_id": context.identity.candidate_id,
            "configuration_digest": context.config_digest,
            "worker_pids": _fault_worker_pids(
                context.record_results, (_STORM_FAULT,)
            ),
            "storms": storm_docs,
        },
    )


def _gate_provenance(context: _GateContext) -> dict[str, Any]:
    identity = context.identity
    pinned = (
        bool(identity.engine_version)
        and all(bool(v) for v in identity.packages.values())
        and all(bool(v) for v in identity.models.values())
        and context.config_digest.startswith("sha256:")
    )
    return _gate(
        "provenance-pinned",
        "passed" if pinned else "failed",
        evidence={
            "engine_version": identity.engine_version,
            "packages": dict(identity.packages),
            "models": dict(identity.models),
        },
    )


_RECEIPT_SAMPLE_COUNT = 3


def _gate_receipt_compatibility(context: _GateContext) -> dict[str, Any]:
    """Build COMPLETE production receipts and validate them for real.

    For three representative sanitized records the gate builds the full
    production receipt shape (``receipt_contract.build_production_receipt``,
    mirroring ``adapter.core.redaction_receipt.sanitize_observation``) and
    validates it against BOTH the external ingest JSON schema definition and
    the literal runtime emission gate
    (``runtime.sinks._require_redaction_receipt``). All three must validate
    with zero errors; the value-free receipts (digests + counts only) become
    the gate evidence (issue #290 defect 3).
    """

    from . import receipt_contract

    samples = [
        r
        for r in context.record_results
        if r.get("outcome") == "sanitized"
        and r["record_id"] in context.sanitized_observations
    ][:_RECEIPT_SAMPLE_COUNT]
    if len(samples) < _RECEIPT_SAMPLE_COUNT:
        return _gate(
            "receipt-contract-compatible",
            "pending",
            evidence={
                "sanitized_records_available": len(samples),
                "required": _RECEIPT_SAMPLE_COUNT,
            },
        )
    affected: list[str] = []
    receipts_evidence: list[dict[str, Any]] = []
    for result in samples:
        record_id = result["record_id"]
        counts: dict[str, int] = {}
        for finding in result.get("findings", []):
            counts[finding["category"]] = counts.get(finding["category"], 0) + 1
        receipt = receipt_contract.build_production_receipt(
            context.identity,
            context.config_digest,
            context.input_observations[record_id],
            context.sanitized_observations[record_id],
            counts,
            _RECEIPT_COMPLETED_AT,
        )
        errors = receipt_contract.validate_production_receipt(receipt)
        receipts_evidence.append(
            {"record_id": record_id, "receipt": receipt, "errors": errors}
        )
        if errors:
            affected.append(record_id)
    return _gate(
        "receipt-contract-compatible",
        "failed" if affected else "passed",
        affected=affected,
        evidence={
            "sample_records": [r["record_id"] for r in samples],
            "validation": (
                "jsonschema definitions.ExternalRedactionReceipt AND "
                "runtime.sinks._require_redaction_receipt"
            ),
            "receipts": receipts_evidence,
        },
    )


def aggregate_gates(gates: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic aggregate over gate statuses.

    Any ``failed`` -> ``failed``; else any ``pending`` -> ``pending``; else
    ``passed``. ``passed`` is True ONLY when every gate actually passed — a
    pending gate is never counted as a pass.
    """

    failed_ids = sorted(g["gate_id"] for g in gates if g["status"] == "failed")
    pending_ids = sorted(g["gate_id"] for g in gates if g["status"] == "pending")
    if failed_ids:
        state = "failed"
    elif pending_ids:
        state = "pending"
    else:
        state = "passed"
    return {
        "aggregate_state": state,
        "passed": state == "passed",
        "pending_gate_ids": pending_ids,
        "failed_gate_ids": failed_ids,
    }


def compute_hard_gates(context: _GateContext, document: dict[str, Any]) -> dict[str, Any]:
    """The full contract gate list, computed value-free from one run."""

    records = context.record_results
    attribution = {
        "candidate_id": context.identity.candidate_id,
        "configuration_digest": context.config_digest,
    }
    timeout_faults = ("hang", _STORM_FAULT)
    crash_faults = ("exception", "worker_crash")
    probe_summaries = [
        {
            key: probe.get(key)
            for key in (
                "payload_class",
                "probe",
                "budget_seconds",
                "outcome",
                "duration_ms",
                "enforced_termination",
            )
        }
        for probe in context.execution_doc.get("production_deadline_probes", [])
    ]
    gates = [
        _gate_no_raw_leakage(context, document),
        _gate_mandatory_protection(context),
        _gate_identity_preservation(context),
        _gate("no-undeclared-network", "pending", evidence="artifact:offline-proof"),
        _fail_closed_gate(
            "fail-closed-unavailable",
            records,
            ("missing_model", "init_failure"),
            {
                "missing_model": "backend_unavailable",
                "init_failure": "backend_unavailable",
            },
        ),
        _fail_closed_gate(
            "fail-closed-invalid-config",
            records,
            ("invalid_configuration",),
            {"invalid_configuration": "backend_invalid_configuration"},
        ),
        _fail_closed_gate(
            "fail-closed-crash",
            records,
            crash_faults,
            {"exception": "backend_crash", "worker_crash": "backend_crash"},
            extra_evidence={
                **attribution,
                "worker_pids": _fault_worker_pids(records, ("worker_crash",)),
            },
        ),
        _fail_closed_gate(
            "fail-closed-timeout",
            records,
            timeout_faults,
            {"hang": "backend_timeout", _STORM_FAULT: "backend_timeout"},
            extra_evidence={
                **attribution,
                "worker_pids": _fault_worker_pids(records, timeout_faults),
                "production_deadline_probes": probe_summaries,
            },
        ),
        _gate_unsupported_content(context),
        _gate_no_envelope_on_failure(context),
        _gate_deterministic(context),
        _gate_bounded_cleanup(context),
        _gate_provenance(context),
        _gate("license-compatible", "pending", evidence="artifact:license-report"),
        _gate_receipt_compatibility(context),
    ]
    return {
        "candidate_id": context.identity.candidate_id,
        **aggregate_gates(gates),
        "gates": gates,
    }


def _gate_unsupported_content(context: _GateContext) -> dict[str, Any]:
    relevant = []
    for result in context.record_results:
        if _fault_of(result):
            continue
        expected = context.expected_by_record.get(result["record_id"], {})
        if expected.get("expected_outcome") == "failed_closed":
            relevant.append((result, expected))
    if not relevant:
        return _gate(
            "fail-closed-unsupported-content",
            "pending",
            evidence="no_records_in_corpus",
        )
    affected = [
        result["record_id"]
        for result, expected in relevant
        if result.get("outcome") != "failed_closed"
        or result.get("failure_reason") != expected.get("expected_failure_reason")
    ]
    return _gate(
        "fail-closed-unsupported-content",
        "failed" if affected else "passed",
        affected=affected,
        evidence={"records_checked": len(relevant)},
    )


# ---------------------------------------------------------------------------
# Preservation assertions (evaluated while sanitized text is in memory)
# ---------------------------------------------------------------------------


def _preservation_block(
    expected: dict[str, Any], sanitized_fields: dict[str, str]
) -> dict[str, Any] | None:
    assertions = expected.get("preservation_assertions") or []
    if not assertions:
        return None
    missing = [
        assertion["assertion_id"]
        for assertion in assertions
        if assertion["required_substring"]
        not in sanitized_fields.get(assertion["field_path"], "")
    ]
    return {"assertions_checked": len(assertions), "missing_assertion_ids": missing}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _identity_from_worker(
    worker_identity: dict[str, Any] | None, fallback: BackendIdentity
) -> BackendIdentity:
    """Prefer the worker's POST-initialize identity over the parent's.

    Heavy backends enrich their identity during ``initialize`` (observed
    package versions, model weight digests); initialization now happens inside
    the worker, so the ready handshake carries the authoritative identity.
    """

    if not worker_identity:
        return fallback
    return BackendIdentity(
        candidate_id=str(worker_identity.get("candidate_id", fallback.candidate_id)),
        family=str(worker_identity.get("family", fallback.family)),
        engine_version=str(
            worker_identity.get("engine_version", fallback.engine_version)
        ),
        packages=dict(worker_identity.get("packages") or {}),
        models=dict(worker_identity.get("models") or {}),
        configuration=dict(worker_identity.get("configuration") or {}),
    )


def run_candidate(
    candidate_id: str,
    *,
    repo_root: Path,
    policy: RedactionPolicy | None = None,
    determinism_repeats: int = 5,
    fault_budget_seconds: float = 2.0,
    prewarm_timeout_seconds: float = _PREWARM_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run one candidate over the whole corpus; return the result document.

    The document is JSON-serializable and value-free: digests, offsets, and
    counts only. Raw corpus values are used in memory to compute the leakage
    and mandatory-protection gates, then discarded.

    Every record (and every determinism repeat) executes inside the
    candidate's worker process under the enforced
    ``policy.per_record_budget_seconds`` deadline. The worker is prewarmed
    once before the record loop (and re-prewarmed after any fault probe that
    killed it); each prewarm is recorded honestly in
    ``execution.prewarm_events``. After the record loop the production
    deadline probes run (``execution.production_deadline_probes``), then all
    hard gates are computed from observed evidence.
    """

    repo_root = Path(repo_root)
    active_policy = policy or RedactionPolicy()
    loader = _corpus_loader()
    manifest_path = repo_root / "tests" / "redaction_evaluation" / "corpus-manifest.json"
    manifest_records = list(loader.iter_manifest(manifest_path))

    # Parent-side backend: identity/label-map access only; initialization —
    # and every analyze call — happens inside the candidate worker.
    backend = create_backend(candidate_id)
    label_map = getattr(
        backend, "label_map", LabelMap(map_id=f"{candidate_id}-labels-unversioned")
    )

    manager = CandidateWorkerManager(candidate_id)
    prewarm_events: list[dict[str, Any]] = []
    try:
        initial_prewarm_seconds = manager.prewarm(prewarm_timeout_seconds)
        prewarm_events.append(
            {
                "phase": "initial",
                "seconds": initial_prewarm_seconds,
                "worker_pid": manager.worker_pid(),
            }
        )
        identity = _identity_from_worker(manager.worker_identity, backend.identity)
        config_digest = configuration_digest(
            dict(identity.configuration), label_map, active_policy
        )
        # From here on every cleanup record is attributable to this exact
        # candidate configuration.
        manager.configuration_digest = config_digest

        sink = RecordingSink()
        cursor = RecordingCursor()
        record_results: list[dict[str, Any]] = []
        sanitized_by_record: dict[str, dict[str, str]] = {}
        sanitized_observations: dict[str, dict[str, Any]] = {}
        input_observations: dict[str, dict[str, Any]] = {}
        expected_by_record: dict[str, dict[str, Any]] = {}
        mismatched: list[str] = []
        unmapped_by_pid: dict[int, dict[str, int]] = {}

        for manifest_record in manifest_records:
            record_id = str(manifest_record["record_id"])
            input_record = loader.load_input_record(
                repo_root / str(manifest_record["input_path"])
            )
            expected_by_record[record_id] = _load_expected(
                repo_root, str(manifest_record["expected_path"])
            )
            input_observations[record_id] = copy.deepcopy(
                input_record.get("observation") or {}
            )
            outcome = process_record(
                input_record,
                backend=backend,
                policy=active_policy,
                classes=manifest_record.get("classes", ()),
                determinism_repeats=determinism_repeats,
                fault_budget_seconds=fault_budget_seconds,
                manager=manager,
            )
            result = outcome.result
            result.setdefault("record_id", record_id)

            # Observed boundary routing: the single production-mirroring
            # decision point; the gate later checks these counts.
            sink_calls_before = sink.call_count
            advances_before = cursor.advance_count
            route_outcome(result, sink, cursor)
            result["observed_sink_calls"] = sink.call_count - sink_calls_before
            result["observed_cursor_advances"] = (
                cursor.advance_count - advances_before
            )
            if result.get("outcome") == "failed_closed":
                result["no_envelope"] = result["observed_sink_calls"] == 0
                result["no_cursor_advance"] = (
                    result["observed_cursor_advances"] == 0
                )

            preservation = _preservation_block(
                expected_by_record[record_id], outcome.sanitized_fields
            )
            if preservation is not None and result.get("outcome") in (
                "sanitized",
                "unchanged",
            ):
                result["preservation"] = preservation
            digests = result.get("repeat_digests") or []
            if len(digests) > 1 and any(d != digests[0] for d in digests[1:]):
                mismatched.append(record_id)
            record_results.append(result)
            if outcome.sanitized_fields:
                sanitized_by_record[record_id] = outcome.sanitized_fields
            if outcome.sanitized_observation is not None:
                sanitized_observations[record_id] = outcome.sanitized_observation
            if outcome.unmapped_snapshot is not None:
                unmapped_by_pid[outcome.unmapped_snapshot["worker_pid"]] = dict(
                    outcome.unmapped_snapshot["labels"]
                )

            # A fault probe may have killed the worker; restore it OUTSIDE
            # the next record's deadline and record the cost honestly.
            if not manager.worker_alive():
                seconds = manager.prewarm(prewarm_timeout_seconds)
                prewarm_events.append(
                    {
                        "phase": f"after-record:{record_id}",
                        "seconds": seconds,
                        "worker_pid": manager.worker_pid(),
                    }
                )

        probes, probe_prewarms = run_production_deadline_probes(
            manager, active_policy, prewarm_timeout_seconds=prewarm_timeout_seconds
        )
        prewarm_events.extend(probe_prewarms)
    finally:
        manager.shutdown()

    # Unmapped labels accumulate per worker generation (a recycled worker
    # restarts its counters); sum the last snapshot of each generation.
    unmapped_labels: dict[str, int] = {}
    for snapshot in unmapped_by_pid.values():
        for label, count in snapshot.items():
            unmapped_labels[label] = unmapped_labels.get(label, 0) + int(count)

    execution_doc: dict[str, Any] = {
        "mode": "candidate-worker-subprocess",
        "candidate_id": candidate_id,
        "configuration_digest": config_digest,
        "worker_prewarm_seconds": initial_prewarm_seconds,
        "worker_pid": prewarm_events[0]["worker_pid"],
        "worker_pids": manager.pids_seen(),
        "per_record_budget_seconds": active_policy.per_record_budget_seconds,
        "prewarm_events": prewarm_events,
        "production_deadline_probes": probes,
    }

    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "identity": {
            "candidate_id": identity.candidate_id,
            "family": identity.family,
            "engine_version": identity.engine_version,
            "packages": dict(identity.packages),
            "models": dict(identity.models),
            "configuration": dict(identity.configuration),
        },
        "configuration_digest": config_digest,
        "corpus_digest": corpus_digest_from_manifest(manifest_records),
        "policy": active_policy.manifest(),
        "execution": execution_doc,
        "records": record_results,
        "unmapped_labels": unmapped_labels,
        "determinism": {
            "repeats": determinism_repeats,
            "mismatched_record_ids": sorted(mismatched),
        },
    }

    context = _GateContext(
        record_results=record_results,
        sanitized_by_record=sanitized_by_record,
        sanitized_observations=sanitized_observations,
        input_observations=input_observations,
        expected_by_record=expected_by_record,
        determinism_mismatches=sorted(mismatched),
        identity=identity,
        config_digest=config_digest,
        policy=active_policy,
        execution_doc=execution_doc,
    )
    document["hard_gates"] = compute_hard_gates(context, document)
    return document
