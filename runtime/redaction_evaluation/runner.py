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

Fail-closed modeling
--------------------
Production semantics on any redaction failure are: no envelope is emitted, no
sink is called, and the ingestion cursor does not advance. That contract is
codified in ``runtime/cursor_policy.py`` ("Sensitive-data rejection is never
silently advanced"; schema/gate failure -> quarantine, not advance) and in
``adapter.core.redaction_receipt.guarded_sanitize_observation`` ("no envelope,
no sink call, no cursor advancement may follow" a typed
:class:`RedactionFailure`). The harness MODELS the same invariant
structurally: every ``failed_closed`` record result carries
``"no_envelope": true`` and ``"no_cursor_advance": true`` and contains no
sanitized content whatsoever (value-free failure).

Raw corpus values live only in memory while hard gates are computed; the
returned document carries digests, offsets, and counts only.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import importlib
import json
import multiprocessing
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from adapter.core.redaction import redact_with_findings
from adapter.core.redaction_receipt import _digest as receipt_digest_of
from adapter.core.sensitive import detect_sensitive

from .backends import create_backend
from .backends.faults import FaultInjectedBackend
from .policy import LabelMap, RedactionPolicy, canonical_digest, configuration_digest
from .seam import BackendError, BackendFinding, BackendIdentity, RedactionBackend

SCHEMA_VERSION = 1

#: Faults whose only honest proof is a hard-terminated child process.
_SUBPROCESS_FAULTS = ("hang", "worker_crash")
_STORM_FAULT = "timeout_storm"
_INIT_FAULTS = ("invalid_configuration", "missing_model", "init_failure")
_STORM_CONCURRENCY = 8
_STORM_JOIN_TOLERANCE_SECONDS = 6.0
_ORPHAN_SETTLE_SECONDS = 3.0
_JOIN_GRACE_SECONDS = 2.0
_SPAWN_TOLERANCE_SECONDS = 5.0

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
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


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
# Fault probes: real subprocess termination proof
# ---------------------------------------------------------------------------


def _fault_probe(fault: str, text: str, budget: float, conn: Any) -> None:
    """Spawned-child probe body (module-level for the ``spawn`` context).

    Builds a :class:`FaultInjectedBackend` around the baseline identity and
    calls ``analyze``; ``worker_crash`` exits abruptly via ``os._exit(3)`` so
    the parent observes a real EOF, never a typed reply.
    """

    from .backends.baseline import BicameralStdlibBackend

    base = BicameralStdlibBackend()
    probe = FaultInjectedBackend(base.identity, fault)
    policy = RedactionPolicy(per_record_budget_seconds=budget)
    if fault == "worker_crash":
        os._exit(3)
    try:
        findings = probe.analyze(text, field_path="excerpt", policy=policy)
    except BackendError as err:
        conn.send(("err", err.reason))
        return
    conn.send(("ok", len(findings)))


def _terminate(process: Any) -> bool:
    """Bounded hard termination; True when the child is verifiably dead."""

    if not process.is_alive():
        return True
    process.terminate()
    process.join(_JOIN_GRACE_SECONDS)
    if process.is_alive():
        kill = getattr(process, "kill", None)
        if callable(kill):
            kill()
        process.join(_JOIN_GRACE_SECONDS)
    return not process.is_alive()


def run_subprocess_fault(
    fault: str, text: str, budget: float
) -> tuple[str, bool, int | None]:
    """Run one fault probe in a spawned child.

    Returns ``(failure_reason, cleanup_ok, child_pid)``. ``hang`` must yield
    ``backend_timeout`` with the child hard-terminated; ``worker_crash`` must
    yield ``backend_crash`` via parent-side EOF.
    """

    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe()
    process = ctx.Process(
        target=_fault_probe, args=(fault, text, budget, child), daemon=True
    )
    process.start()
    child.close()
    wait = budget if fault == "hang" else budget + _SPAWN_TOLERANCE_SECONDS
    reason = "backend_timeout"
    try:
        if parent.poll(wait):
            try:
                kind, payload = parent.recv()
            except (EOFError, OSError):
                reason = "backend_crash"
            else:
                reason = str(payload) if kind == "err" else "backend_no_failure"
        else:
            reason = "backend_timeout"
    finally:
        try:
            parent.close()
        except OSError:
            pass
        cleanup_ok = _terminate(process)
    return reason, cleanup_ok, process.pid


def _python_children() -> set[int]:
    try:
        psutil = importlib.import_module("psutil")
    except ImportError:
        return set()
    pids: set[int] = set()
    for child in psutil.Process().children(recursive=True):
        try:
            if "python" in child.name().lower():
                pids.add(child.pid)
        except psutil.Error:
            continue
    return pids


def run_timeout_storm(
    text: str,
    budget: float,
    backend: RedactionBackend,
    policy: RedactionPolicy,
    *,
    concurrency: int = _STORM_CONCURRENCY,
) -> dict[str, Any]:
    """Concurrent hang probes: all must time out, leave no orphan, and the
    pipeline must recover immediately afterwards."""

    try:
        importlib.import_module("psutil")
        psutil_available = True
    except ImportError:
        psutil_available = False
    before = _python_children()

    reasons: list[str | None] = [None] * concurrency
    cleanups: list[bool] = [False] * concurrency

    def _one(slot: int) -> None:
        reason, cleanup_ok, _pid = run_subprocess_fault("hang", text, budget)
        reasons[slot] = reason
        cleanups[slot] = cleanup_ok

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
    if psutil_available:
        settle_deadline = time.monotonic() + _ORPHAN_SETTLE_SECONDS
        leftover = _python_children() - before
        while leftover and time.monotonic() < settle_deadline:
            time.sleep(0.1)
            leftover = _python_children() - before
        orphans = len(leftover)

    healthy = {
        "source_ref": {
            "source_id": "storm-recovery",
            "ref": "storm-recovery-ref",
            "url": "",
            "kind": "synthetic",
        },
        "excerpt": "storm recovery probe with no sensitive content",
        "title": "recovery",
        "author": "harness",
        "mode": "batch",
        "timestamp": "2026-01-01T00:00:00Z",
        "provider_event_id": "storm-recovery-event",
        "provider_resource_id": "storm-recovery-resource",
        "evidence_id": "storm-recovery-evidence",
        "evidence_metadata": {},
        "metadata": {},
    }
    recovery = execute_once(healthy, backend, policy)
    return {
        "storm_concurrency": concurrency,
        "all_timed_out": all_timed_out,
        "cleanup_ok": all(cleanups),
        "orphans": orphans if orphans is not None else -1,
        "recovered": recovery.outcome in ("sanitized", "unchanged"),
    }


# ---------------------------------------------------------------------------
# Per-record processing (dispatches normal records and every fault class)
# ---------------------------------------------------------------------------


@dataclass
class ProcessOutcome:
    """Per-record harness output plus in-memory-only value-bearing context."""

    result: dict[str, Any]
    sanitized_fields: dict[str, str] = field(default_factory=dict)
    sanitized_observation: dict[str, Any] | None = None


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
            # Structural fail-closed assertions; see module docstring and
            # runtime/cursor_policy.py.
            "no_envelope": True,
            "no_cursor_advance": True,
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
) -> ProcessOutcome:
    """Execute one corpus input record end-to-end (all fault classes included)."""

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
            fault, base, observation, backend, policy, fault_budget_seconds
        )
        result["duration_ms"] = (time.perf_counter() - started) * 1000.0
        result["fault"] = fault
        return ProcessOutcome(result=result)

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


def _run_fault_record(
    fault: str,
    base: dict[str, Any],
    observation: dict[str, Any],
    backend: RedactionBackend,
    policy: RedactionPolicy,
    fault_budget_seconds: float,
) -> dict[str, Any]:
    probe_text = str(observation.get("excerpt", ""))

    if fault in _SUBPROCESS_FAULTS:
        reason, cleanup_ok, _pid = run_subprocess_fault(
            fault, probe_text, fault_budget_seconds
        )
        return _failure_result(base, reason, extra={"cleanup_ok": cleanup_ok})

    if fault == _STORM_FAULT:
        storm = run_timeout_storm(probe_text, fault_budget_seconds, backend, policy)
        reason = "backend_timeout" if storm["all_timed_out"] else "storm_incomplete"
        return _failure_result(base, reason, extra={"storm": storm})

    fault_backend = FaultInjectedBackend(backend.identity, fault)

    if fault in _INIT_FAULTS:
        try:
            fault_backend.initialize()
        except BackendError as err:
            return _failure_result(base, err.reason)
        except Exception:
            return _failure_result(base, "backend_crash")
        return _failure_result(base, "fault_did_not_fire")

    if fault == "nondeterministic":
        first = fault_backend.analyze(probe_text, field_path="excerpt", policy=policy)
        second = fault_backend.analyze(probe_text, field_path="excerpt", policy=policy)
        if first != second:
            return _failure_result(base, "nondeterministic_backend_output")
        return _failure_result(base, "fault_did_not_fire")

    # In-process faults: exception, malformed spans; run the normal pipeline
    # with the fault backend so validation/typing behaves exactly as it would
    # for a real misbehaving candidate.
    execution = execute_once(observation, fault_backend, policy)
    if execution.outcome == "failed_closed":
        return _failure_result(
            base,
            execution.failure_reason or "unknown_failure",
            identity_digests=execution.identity_digests,
            post_screen_hits=execution.post_screen_hits,
        )
    return _failure_result(base, "fault_did_not_fire")


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
    return _gate(
        gate_id,
        "failed" if affected else "passed",
        affected=affected,
        evidence={"records_checked": len(relevant)},
    )


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
    affected = [
        r["record_id"]
        for r in context.record_results
        if r.get("outcome") == "failed_closed"
        and (
            r.get("no_envelope") is not True
            or r.get("no_cursor_advance") is not True
            or "field_digests" in r
            or "findings" in r
        )
    ]
    failed_count = sum(
        1 for r in context.record_results if r.get("outcome") == "failed_closed"
    )
    return _gate(
        "no-envelope-no-cursor-on-failure",
        "failed" if affected else "passed",
        affected=affected,
        evidence={"failed_closed_records": failed_count},
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
    evidence = []
    for result in storms:
        storm = result.get("storm", {})
        evidence.append(storm)
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
        evidence=evidence,
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


def _gate_receipt_compatibility(context: _GateContext) -> dict[str, Any]:
    """Build production-shaped receipts for sample sanitized records.

    Mirrors the receipt contract of ``adapter.core.redaction_receipt``:
    schema_version / engine / engine_version / ruleset digest / input+output
    digests / value-free category-count findings.
    """

    samples = [
        r
        for r in context.record_results
        if r.get("outcome") == "sanitized" and r["record_id"] in
        context.sanitized_observations
    ][:3]
    if not samples:
        return _gate(
            "receipt-contract-compatible", "pending", evidence="no_sanitized_records"
        )
    affected: list[str] = []
    for result in samples:
        record_id = result["record_id"]
        counts: dict[str, int] = {}
        for finding in result.get("findings", []):
            counts[finding["category"]] = counts.get(finding["category"], 0) + 1
        findings_entries = [
            {"category": category, "action": "tokenized", "count": count}
            for category, count in sorted(counts.items())
        ]
        receipt: dict[str, Any] = {
            "schema_version": 1,
            "engine": context.identity.candidate_id,
            "engine_version": context.identity.engine_version,
            "ruleset_digest": context.config_digest,
            "input_digest": receipt_digest_of(
                context.input_observations[record_id]
            ),
            "output_digest": receipt_digest_of(
                context.sanitized_observations[record_id]
            ),
            "findings": findings_entries,
        }
        try:
            json.dumps(receipt, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):
            affected.append(record_id)
            continue
        for entry in findings_entries:
            if set(entry) != {"category", "action", "count"}:
                affected.append(record_id)
                break
    return _gate(
        "receipt-contract-compatible",
        "failed" if affected else "passed",
        affected=affected,
        evidence={"sample_records": [r["record_id"] for r in samples]},
    )


def compute_hard_gates(context: _GateContext, document: dict[str, Any]) -> dict[str, Any]:
    """The full contract gate list, computed value-free from one run."""

    records = context.record_results
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
            ("exception", "worker_crash"),
            {"exception": "backend_crash", "worker_crash": "backend_crash"},
        ),
        _fail_closed_gate(
            "fail-closed-timeout",
            records,
            ("hang", _STORM_FAULT),
            {"hang": "backend_timeout", _STORM_FAULT: "backend_timeout"},
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
        "passed": not any(gate["status"] == "failed" for gate in gates),
        "pending_gate_ids": [g["gate_id"] for g in gates if g["status"] == "pending"],
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


def run_candidate(
    candidate_id: str,
    *,
    repo_root: Path,
    policy: RedactionPolicy | None = None,
    determinism_repeats: int = 5,
    fault_budget_seconds: float = 2.0,
) -> dict[str, Any]:
    """Run one candidate over the whole corpus; return the result document.

    The document is JSON-serializable and value-free: digests, offsets, and
    counts only. Raw corpus values are used in memory to compute the leakage
    and mandatory-protection gates, then discarded.
    """

    repo_root = Path(repo_root)
    active_policy = policy or RedactionPolicy()
    loader = _corpus_loader()
    manifest_path = repo_root / "tests" / "redaction_evaluation" / "corpus-manifest.json"
    manifest_records = list(loader.iter_manifest(manifest_path))

    backend = create_backend(candidate_id)
    backend.initialize()
    label_map = getattr(
        backend, "label_map", LabelMap(map_id=f"{candidate_id}-labels-unversioned")
    )
    config_digest = configuration_digest(
        dict(backend.identity.configuration), label_map, active_policy
    )

    record_results: list[dict[str, Any]] = []
    sanitized_by_record: dict[str, dict[str, str]] = {}
    sanitized_observations: dict[str, dict[str, Any]] = {}
    input_observations: dict[str, dict[str, Any]] = {}
    expected_by_record: dict[str, dict[str, Any]] = {}
    mismatched: list[str] = []

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
        )
        result = outcome.result
        result.setdefault("record_id", record_id)
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

    unmapped_raw = getattr(backend, "unmapped_labels", None)
    unmapped_labels = dict(unmapped_raw) if isinstance(unmapped_raw, dict) else {}

    identity = backend.identity
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
    )
    document["hard_gates"] = compute_hard_gates(context, document)
    return document
