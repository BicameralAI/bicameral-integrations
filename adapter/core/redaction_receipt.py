# SPDX-License-Identifier: MIT
"""Mandatory pre-Bot redaction with deterministic, value-free receipts.

Provider authenticity is verified before this module is called. The sanitizer
then removes sensitive material from Bot-bound text and metadata while keeping
provider and evidence identity stable. Unsupported or unsafe identity content
fails closed rather than being silently rewritten.
"""

from __future__ import annotations

import hashlib
import json
import atexit
import multiprocessing
import os
import threading
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from .observations import Observation
from .redaction import redact_with_findings
from .sensitive import detect_sensitive

ENGINE = "bicameral-stdlib-redaction"
ENGINE_VERSION = "1.0.0"
RULESET_ID = "fx-sec-001-plus-pii-v1"
_RULESET_MANIFEST = {
    "catalog": "FX-SEC-001/v1",
    "detectors": ["secret", "phi", "pan", "email", "phone"],
    "replacement": "[redacted:<category>]",
    "identity_policy": "preserve-opaque-identifiers; hard-catalog-fail-closed",
    "metadata_policy": "recursive-values; sensitive-keys-rejected",
}
RULESET_DIGEST = "sha256:" + hashlib.sha256(
    json.dumps(_RULESET_MANIFEST, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
).hexdigest()


class RedactionFailure(ValueError):
    """Typed hard failure that never includes the rejected sensitive value."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"redaction_failed:{reason}")


def _canonical(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _canonical(sub)
            for key, sub in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, set):
        return sorted(
            (_canonical(item) for item in value),
            key=lambda item: json.dumps(item, sort_keys=True),
        )
    raise RedactionFailure(f"unsupported_metadata_type:{type(value).__name__}")


def _digest(value: object) -> str:
    encoded = json.dumps(
        _canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _observation_payload(observation: Observation) -> dict[str, object]:
    return {
        "source_ref": {
            "source_id": observation.source_ref.source_id,
            "ref": observation.source_ref.ref,
            "url": observation.source_ref.url,
            "kind": observation.source_ref.kind,
        },
        "excerpt": observation.excerpt,
        "title": observation.title,
        "mode": observation.mode.value,
        "author": observation.author,
        "timestamp": observation.timestamp,
        "provider_event_id": observation.provider_event_id,
        "provider_resource_id": observation.provider_resource_id,
        "evidence_id": observation.evidence_id,
        "evidence_metadata": observation.evidence_metadata,
        "metadata": observation.metadata,
    }


def _preserve_identity(value: str, field: str) -> str:
    """Preserve opaque provider identity byte-for-byte unless the hard catalog hits.

    Generic email and phone heuristics are intentionally excluded here because UUIDs,
    timestamps, document IDs, and source refs routinely contain phone-like digit runs.
    Identity is structural, not free-text. A secret, PHI label, or valid PAN still fails
    closed through the hard catalog.
    """

    if detect_sensitive(value):
        raise RedactionFailure(f"sensitive_identity_field:{field}")
    return value


def _merge_counts(target: dict[str, int], found: dict[str, int]) -> None:
    for category, count in found.items():
        target[category] = target.get(category, 0) + count


def _sanitize_text(value: str, findings: dict[str, int]) -> str:
    redacted, found = redact_with_findings(value)
    _merge_counts(findings, found)
    return redacted


def _sanitize_value(
    value: object,
    findings: dict[str, int],
    *,
    path: str,
) -> object:
    if isinstance(value, str):
        return _sanitize_text(value, findings)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, bytes):
        raise RedactionFailure(f"unsupported_binary:{path}")
    if isinstance(value, dict):
        output: dict[object, object] = {}
        for key, sub in value.items():
            key_text = str(key)
            redacted_key, key_findings = redact_with_findings(key_text)
            if redacted_key != key_text or any(key_findings.values()):
                raise RedactionFailure(f"sensitive_metadata_key:{path}")
            output[key] = _sanitize_value(
                sub,
                findings,
                path=f"{path}.{key_text}",
            )
        return output
    if isinstance(value, list):
        return [
            _sanitize_value(item, findings, path=f"{path}[]") for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            _sanitize_value(item, findings, path=f"{path}[]") for item in value
        )
    if isinstance(value, set):
        raise RedactionFailure(f"unsupported_metadata_type:set:{path}")
    raise RedactionFailure(f"unsupported_metadata_type:{type(value).__name__}")


def _sanitize_mapping(
    value: dict[str, object],
    findings: dict[str, int],
    *,
    path: str,
) -> dict[str, object]:
    sanitized = _sanitize_value(value, findings, path=path)
    if not isinstance(sanitized, dict):
        raise RedactionFailure(f"sanitized_mapping_invalid:{path}")
    return {str(key): sub for key, sub in sanitized.items()}


def sanitize_observation(
    observation: Observation,
    *,
    completed_at: str | None = None,
) -> tuple[Observation, dict[str, object]]:
    """Return a sanitized Observation plus a deterministic, value-free receipt."""

    input_payload = _observation_payload(observation)
    findings: dict[str, int] = {}

    # Identity and ordering fields remain byte-for-byte stable or the boundary fails.
    _preserve_identity(observation.source_ref.source_id, "source_ref.source_id")
    _preserve_identity(observation.source_ref.ref, "source_ref.ref")
    _preserve_identity(observation.source_ref.url, "source_ref.url")
    _preserve_identity(observation.source_ref.kind, "source_ref.kind")
    _preserve_identity(observation.provider_event_id, "provider_event_id")
    _preserve_identity(observation.provider_resource_id, "provider_resource_id")
    _preserve_identity(observation.evidence_id, "evidence_id")
    _preserve_identity(observation.timestamp, "timestamp")

    sanitized = replace(
        observation,
        excerpt=_sanitize_text(observation.excerpt, findings),
        title=_sanitize_text(observation.title, findings),
        author=_sanitize_text(observation.author, findings),
        evidence_metadata=_sanitize_mapping(
            observation.evidence_metadata,
            findings,
            path="evidence_metadata",
        ),
        metadata=_sanitize_mapping(
            observation.metadata,
            findings,
            path="metadata",
        ),
    )
    output_payload = _observation_payload(sanitized)

    receipt = {
        "schema_version": 1,
        "engine": ENGINE,
        "engine_version": ENGINE_VERSION,
        "ruleset_id": RULESET_ID,
        "ruleset_digest": RULESET_DIGEST,
        "input_digest": _digest(input_payload),
        "output_digest": _digest(output_payload),
        "findings": [
            {"category": category, "action": "tokenized", "count": count}
            for category, count in sorted(findings.items())
            if count > 0
        ],
        "structural_fields_preserved": True,
        "completed_at": completed_at
        or datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }
    return sanitized, receipt


# ---------------------------------------------------------------------------
# Guarded boundary entry (GH #260 typed-failure completion)
# ---------------------------------------------------------------------------

_GATE_MAX_BYTES = 1_048_576  # 1 MiB serialized-observation budget
_GATE_BUDGET_SECONDS = 5.0


def _worker_loop(conn: Any) -> None:
    """Sanitizer worker: one recyclable child process.

    Receives ``(observation, completed_at)`` pairs and replies with either
    ``("ok", (sanitized, receipt))`` or ``("err", reason_code)``. Only typed
    reason codes cross the process boundary on failure — never exception text,
    never payload content — so a raw sensitive value cannot leak through the
    failure channel. The test-only hang hook (environment variable
    ``BICAMERAL_REDACTION_TEST_SLEEP_S``) exists so timeout isolation can be
    proven without depending on a pathological input; production code never
    sets it.
    """
    sleep_s = float(os.environ.get("BICAMERAL_REDACTION_TEST_SLEEP_S", "0") or 0)
    while True:
        try:
            observation, completed_at = conn.recv()
        except (EOFError, OSError):
            return
        if sleep_s:
            import time

            time.sleep(sleep_s)
        try:
            result = sanitize_observation(observation, completed_at=completed_at)
        except RedactionFailure as failure:
            conn.send(("err", failure.reason))
        except Exception:
            # Unknown engine crash: typed, value-free.
            conn.send(("err", "engine_unavailable"))
        else:
            conn.send(("ok", result))


class _WorkerManager:
    """Bounded, recyclable sanitizer worker (GH #269 rounds 3-4).

    Exactly one child process serves sanitization. The caller's
    ``budget_seconds`` is ONE absolute monotonic deadline covering the whole
    guarded operation — lock acquisition, worker availability/spawn, payload
    send, worker execution, and response — so a concurrent caller waiting on
    the lock can never silently exceed its own budget. On timeout the child is
    hard-terminated (terminate, bounded join, then kill where the platform
    supports it, bounded join again) and discarded; cleanup is bounded by
    ``CLEANUP_TOLERANCE_SECONDS``, the only documented amount by which a
    caller may exceed its declared budget. Repeated timeouts recycle rather
    than accumulate workers, so a timeout storm cannot starve later healthy
    requests. Workers are daemonic and atexit-terminated: shutdown never
    hangs on abandoned sanitizer work.
    """

    # Documented cleanup tolerance: terminate-join (2s) + kill-join (2s) plus
    # scheduling margin. This is a hard bound, never a second unbounded wait.
    CLEANUP_TOLERANCE_SECONDS = 5.0
    _JOIN_GRACE_SECONDS = 2.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ctx = multiprocessing.get_context("spawn")
        self._process: multiprocessing.process.BaseProcess | None = None
        # Platform pipe types diverge (PipeConnection on Windows); typed loosely.
        self._conn: Any = None
        self.last_cleanup_outcome = ""
        atexit.register(self._shutdown)

    def _spawn(self) -> None:
        parent, child = self._ctx.Pipe()
        process = self._ctx.Process(target=_worker_loop, args=(child,), daemon=True)
        process.start()
        child.close()
        self._process, self._conn = process, parent

    def _kill(self) -> None:
        """Bounded forced termination; records a typed, value-free outcome."""
        outcome = "no_worker"
        try:
            if self._conn is not None:
                try:
                    self._conn.close()
                except OSError:
                    pass
            process = self._process
            if process is not None and process.is_alive():
                outcome = "terminated"
                try:
                    process.terminate()
                    process.join(timeout=self._JOIN_GRACE_SECONDS)
                    if process.is_alive():
                        kill = getattr(process, "kill", None)
                        if callable(kill):
                            outcome = "killed"
                            kill()
                        else:  # pragma: no cover - all supported platforms have kill()
                            outcome = "terminate_only_platform"
                        process.join(timeout=self._JOIN_GRACE_SECONDS)
                    if process.is_alive():  # pragma: no cover - defensive
                        outcome = "kill_failed"
                except (OSError, ValueError):  # pragma: no cover - defensive
                    outcome = "cleanup_error"
            if process is not None:
                try:
                    process.close()
                except (OSError, ValueError):
                    pass
        finally:
            # References are cleared even when termination raised.
            self._process, self._conn = None, None
            self.last_cleanup_outcome = outcome

    def _shutdown(self) -> None:  # pragma: no cover - interpreter exit path
        if self._lock.acquire(timeout=self._JOIN_GRACE_SECONDS):
            try:
                self._kill()
            finally:
                self._lock.release()

    def reset_for_tests(self) -> None:
        """Discard the current worker so the next call spawns with the current
        environment. Test seam only; production code never calls it."""
        with self._lock:
            self._kill()

    def worker_alive(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.is_alive()

    def call(
        self, observation: Observation, completed_at: str | None, budget_seconds: float
    ) -> tuple[Observation, dict[str, object]]:
        import time

        deadline = time.monotonic() + budget_seconds

        def remaining() -> float:
            return deadline - time.monotonic()

        # Lock acquisition consumes the caller's own budget: a caller queued
        # behind a hung worker times out on ITS deadline, never on the hung
        # caller's, so concurrent callers cannot form an unbounded queue.
        lock_wait = remaining()
        if lock_wait <= 0 or not self._lock.acquire(timeout=lock_wait):
            raise RedactionFailure("timeout")
        try:
            if self._process is None or not self._process.is_alive():
                self._kill()
                self._spawn()
            assert self._conn is not None
            try:
                self._conn.send((observation, completed_at))
            except (ValueError, TypeError, AttributeError, OSError):
                # Unpicklable observation content cannot enter the worker.
                self._kill()
                raise RedactionFailure("unsupported_payload") from None
            poll_wait = remaining()
            if poll_wait <= 0 or not self._conn.poll(poll_wait):
                # HARD termination within the documented cleanup tolerance:
                # the stuck worker is killed and replaced, never abandoned.
                # Its partial work dies with the process, so timed-out work
                # can never later mutate shared state.
                self._kill()
                raise RedactionFailure("timeout")
            try:
                kind, payload = self._conn.recv()
            except (EOFError, OSError):
                self._kill()
                raise RedactionFailure("engine_unavailable") from None
            if kind == "err":
                raise RedactionFailure(str(payload))
            sanitized, receipt = payload
            return sanitized, receipt
        finally:
            self._lock.release()


_WORKER = _WorkerManager()


def guarded_sanitize_observation(
    observation: Observation,
    *,
    completed_at: str | None = None,
    max_bytes: int = _GATE_MAX_BYTES,
    budget_seconds: float = _GATE_BUDGET_SECONDS,
    engine: object | None = True,
) -> tuple[Observation, dict[str, object]]:
    """``sanitize_observation`` with the full GH #260 typed-failure envelope.

    Adds the boundary guards the inner sanitizer does not own, each failing
    closed with a typed :class:`RedactionFailure` reason (no envelope, no sink
    call, no cursor advancement may follow):

    - ``engine_unavailable`` — the redaction engine is not importable/configured;
    - ``invalid_ruleset`` — the deterministic ruleset identity cannot be
      established (empty digest/id would make receipts unverifiable);
    - ``oversized_payload`` — serialized observation content exceeds the budget;
    - ``timeout`` — sanitization exceeded its wall-clock budget; the worker
      process is hard-terminated and recycled, so a stuck sanitizer cannot
      reduce healthy throughput;
    - ``receipt_generation_failure`` — the receipt could not be built/serialized;
    - plus the inner sanitizer's own ``unsupported_*``, ``sensitive_*``, and
      structural reasons, which pass through unchanged. Content the engine
      cannot safely transform surfaces as ``sensitive_identity_field`` /
      ``sensitive_metadata_key`` (prohibited content, rejected).
    """
    if engine is None:
        raise RedactionFailure("engine_unavailable")
    if not RULESET_ID or not RULESET_DIGEST.startswith("sha256:"):
        raise RedactionFailure("invalid_ruleset")

    try:
        serialized = json.dumps(
            _canonical(_observation_payload(observation)),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    except RedactionFailure:
        raise
    except (TypeError, ValueError):
        raise RedactionFailure("unsupported_payload") from None
    if len(serialized.encode("utf-8")) > max_bytes:
        raise RedactionFailure("oversized_payload")

    # Bounded enforcement with real termination: sanitization runs in a
    # recyclable child process; on timeout the child is hard-terminated and
    # replaced (see _WorkerManager). Caller latency AND resource consumption
    # are both bounded — no abandoned thread backs this timeout claim.
    sanitized, receipt = _WORKER.call(observation, completed_at, budget_seconds)

    try:
        json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        raise RedactionFailure("receipt_generation_failure") from None
    return sanitized, receipt


def receipt_digest(receipt: dict[str, object]) -> str:
    """Deterministic ``sha256:`` identity of a receipt.

    Digest domain: every receipt field EXCEPT ``completed_at`` — the only
    observation timestamp, explicitly excluded so the same logical sanitized
    output yields the same receipt identity across runs (GH #260).
    """
    payload = {key: value for key, value in receipt.items() if key != "completed_at"}
    return _digest(payload)
