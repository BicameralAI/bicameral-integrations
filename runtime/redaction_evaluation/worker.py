# SPDX-License-Identifier: MIT
"""Per-candidate sanitizer worker manager (issue #290 remediation).

Mirrors the production worker pattern in
``adapter.core.redaction_receipt._WorkerManager`` — one recyclable spawned
child process, ONE absolute monotonic deadline per call covering lock wait,
lazy spawn + ready handshake, payload send, poll, and receive — but is
parameterized by candidate: the child builds the ACTUAL candidate backend via
``backends.create_backend(candidate_id)`` and initializes it inside the child,
so a timeout or crash probe terminates a real candidate engine, never a
baseline stand-in.

Failure semantics are typed and value-free (:class:`WorkerFailure`):

- ``backend_timeout`` — the caller's deadline expired anywhere in the guarded
  operation; the child is hard-terminated (terminate, bounded join, kill,
  bounded join) and the cleanup outcome is recorded in :attr:`last_cleanup`;
- ``backend_crash`` — the pipe hit EOF or the child exited abruptly;
- ``backend_unavailable`` (or the child's typed init reason) — the candidate
  could not be provisioned/initialized inside the child.

``prewarm`` spawns and waits for the ready handshake OUTSIDE any record
deadline and returns the honestly measured elapsed seconds, so evidence can
separate initialization cost from per-record enforcement. A call that finds
the worker dead spawns lazily INSIDE the caller's budget, exactly like
production lazy-spawn semantics.
"""

from __future__ import annotations

import atexit
import importlib
import multiprocessing
import os
import threading
import time
from typing import Any

_JOIN_GRACE_SECONDS = 2.0
_HANG_SLEEP_SECONDS = 3600.0


class WorkerFailure(Exception):
    """Typed candidate-worker failure; ``reason`` is always value-free."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _policy_from_manifest(manifest: dict[str, Any]) -> Any:
    """Rebuild the parent's ``RedactionPolicy`` inside the child process."""

    from .policy import RedactionPolicy

    return RedactionPolicy(
        policy_id=str(manifest["policy_id"]),
        admitted_text_fields=tuple(manifest["admitted_text_fields"]),
        admitted_tree_fields=tuple(manifest["admitted_tree_fields"]),
        identity_fields=tuple(manifest["identity_fields"]),
        categories=tuple(manifest["categories"]),
        replacement_template=str(manifest["replacement_template"]),
        overlap_rule=str(manifest["overlap_rule"]),
        per_record_budget_seconds=float(manifest["per_record_budget_seconds"]),
        max_payload_bytes=int(manifest["max_payload_bytes"]),
    )


def _safe_send(conn: Any, message: Any) -> None:
    try:
        conn.send(message)
    except (OSError, ValueError):
        pass


def _identity_doc(identity: Any) -> dict[str, Any]:
    return {
        "candidate_id": identity.candidate_id,
        "family": identity.family,
        "engine_version": identity.engine_version,
        "packages": dict(identity.packages),
        "models": dict(identity.models),
        "configuration": dict(identity.configuration),
    }


def _candidate_worker_loop(candidate_id: str, conn: Any) -> None:
    """Spawn target: build + initialize the candidate, then serve records.

    Protocol (all replies typed and value-free on failure):

    - on successful initialization: ``("ready", {candidate_id, pid, identity})``
      where ``identity`` is the POST-initialize identity (heavy backends enrich
      versions/digests during ``initialize``);
    - on initialization failure: ``("init_err", typed_reason)`` then exit;
    - per request ``("record", payload)`` with payload
      ``{"observation", "policy_manifest", "directives"}``: replies
      ``("ok", result_doc)`` or ``("err", typed_reason)``. Directives
      ``{"fault": "hang"}`` sleep before executing so the parent's deadline is
      the only way out; ``{"fault": "worker_crash"}`` exits abruptly via
      ``os._exit(3)`` so the parent observes a real EOF.
    """

    from .backends import create_backend
    from .seam import BackendError

    try:
        backend = create_backend(candidate_id)
        backend.initialize()
    except BackendError as err:
        _safe_send(conn, ("init_err", err.reason))
        return
    except Exception:
        _safe_send(conn, ("init_err", "backend_unavailable"))
        return
    _safe_send(
        conn,
        (
            "ready",
            {
                "candidate_id": candidate_id,
                "pid": os.getpid(),
                "identity": _identity_doc(backend.identity),
            },
        ),
    )
    while True:
        try:
            message = conn.recv()
        except (EOFError, OSError):
            return
        try:
            kind, payload = message
        except (TypeError, ValueError):
            _safe_send(conn, ("err", "malformed_request"))
            continue
        if kind != "record" or not isinstance(payload, dict):
            _safe_send(conn, ("err", "malformed_request"))
            continue
        directives = dict(payload.get("directives") or {})
        fault = directives.get("fault")
        if fault == "worker_crash":
            os._exit(3)
        if fault == "hang":
            time.sleep(_HANG_SLEEP_SECONDS)
        try:
            from .runner import execute_record_in_worker
            from .seam import BackendError as _BackendError

            policy = _policy_from_manifest(payload["policy_manifest"])
            result = execute_record_in_worker(
                backend, payload["observation"], policy, directives
            )
        except _BackendError as err:
            _safe_send(conn, ("err", err.reason))
            continue
        except Exception:
            # Typed, value-free: never exception text across the boundary.
            _safe_send(conn, ("err", "harness_error"))
            continue
        result["worker_pid"] = os.getpid()
        unmapped = getattr(backend, "unmapped_labels", None)
        result["unmapped_labels"] = (
            dict(unmapped) if isinstance(unmapped, dict) else {}
        )
        _safe_send(conn, ("ok", result))


class CandidateWorkerManager:
    """One recyclable candidate worker; production deadline semantics.

    The caller's ``budget_seconds`` is ONE absolute monotonic deadline covering
    lock acquisition, worker availability (including lazy spawn + ready
    handshake when the worker is dead — initialization inside the caller's
    budget, exactly like production), payload send, poll, and receive. On
    expiry the child is hard-terminated within a bounded cleanup (terminate,
    join, kill, join; the post-kill liveness check is recorded as the cleanup
    outcome — ``kill_failed`` marks the assertion "not alive" failing) and the
    typed failure is raised. Repeated timeouts recycle rather than accumulate
    workers.
    """

    def __init__(self, candidate_id: str, configuration_digest: str = "") -> None:
        self.candidate_id = candidate_id
        self.configuration_digest = configuration_digest
        self._lock = threading.Lock()
        self._ctx = multiprocessing.get_context("spawn")
        self._process: Any = None
        self._conn: Any = None
        self._worker_pid: int | None = None
        self._pids_seen: list[int] = []
        #: POST-initialize identity reported by the child's ready handshake.
        self.worker_identity: dict[str, Any] | None = None
        #: Value-free record of the most recent forced cleanup.
        self.last_cleanup: dict[str, Any] = {}
        atexit.register(self.shutdown)

    # -- locked internals ---------------------------------------------------

    def _spawn_locked(self) -> None:
        parent, child = self._ctx.Pipe()
        process = self._ctx.Process(
            target=_candidate_worker_loop,
            args=(self.candidate_id, child),
            daemon=True,
        )
        process.start()
        child.close()
        self._process, self._conn = process, parent
        if process.pid is not None:
            self._pids_seen.append(int(process.pid))

    def _await_ready_locked(self, deadline: float) -> None:
        assert self._conn is not None
        wait = deadline - time.monotonic()
        if wait <= 0 or not self._conn.poll(wait):
            self._kill_locked()
            raise WorkerFailure("backend_timeout")
        try:
            kind, payload = self._conn.recv()
        except (EOFError, OSError):
            self._kill_locked()
            raise WorkerFailure("backend_crash") from None
        if kind == "init_err":
            reason = str(payload) if payload else "backend_unavailable"
            self._kill_locked()
            raise WorkerFailure(reason)
        if kind != "ready" or not isinstance(payload, dict):
            self._kill_locked()
            raise WorkerFailure("backend_unavailable")
        pid = payload.get("pid")
        self._worker_pid = (
            int(pid) if isinstance(pid, int) else self._process.pid
        )
        identity = payload.get("identity")
        if isinstance(identity, dict):
            self.worker_identity = identity

    def _kill_locked(self) -> None:
        """Bounded hard termination; records a value-free cleanup outcome."""

        started = time.monotonic()
        outcome = "no_worker"
        process = self._process
        pid = self._worker_pid
        if pid is None and process is not None:
            pid = process.pid
        try:
            if self._conn is not None:
                try:
                    self._conn.close()
                except OSError:
                    pass
            if process is not None and process.is_alive():
                outcome = "terminated"
                try:
                    process.terminate()
                    process.join(timeout=_JOIN_GRACE_SECONDS)
                    if process.is_alive():
                        kill = getattr(process, "kill", None)
                        if callable(kill):
                            outcome = "killed"
                            kill()
                        else:  # pragma: no cover - all supported platforms
                            outcome = "terminate_only_platform"
                        process.join(timeout=_JOIN_GRACE_SECONDS)
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
            self._process, self._conn, self._worker_pid = None, None, None
            self.last_cleanup = {
                "outcome": outcome,
                "candidate_id": self.candidate_id,
                "configuration_digest": self.configuration_digest,
                "pid": pid,
                "duration_ms": (time.monotonic() - started) * 1000.0,
            }

    # -- public API ---------------------------------------------------------

    def prewarm(self, timeout_seconds: float) -> float:
        """Spawn + await ready OUTSIDE any record deadline; return elapsed s.

        Returns quickly (near 0.0) when the worker is already alive. The
        elapsed time is recorded honestly by callers as evidence
        (``worker_prewarm_seconds``); it is never blended into a record's
        enforcement budget.
        """

        started = time.monotonic()
        deadline = started + timeout_seconds
        wait = deadline - time.monotonic()
        if wait <= 0 or not self._lock.acquire(timeout=wait):
            raise WorkerFailure("backend_timeout")
        try:
            if self._process is not None and self._process.is_alive():
                return time.monotonic() - started
            self._kill_locked()
            self._spawn_locked()
            self._await_ready_locked(deadline)
        finally:
            self._lock.release()
        return time.monotonic() - started

    def call(
        self,
        observation: dict[str, Any],
        policy: Any,
        directives: dict[str, Any],
        budget_seconds: float,
    ) -> dict[str, Any]:
        """Execute one record in the candidate worker under ONE deadline."""

        deadline = time.monotonic() + budget_seconds
        wait = deadline - time.monotonic()
        if wait <= 0 or not self._lock.acquire(timeout=wait):
            raise WorkerFailure("backend_timeout")
        try:
            if self._process is None or not self._process.is_alive():
                # Lazy spawn INSIDE the caller's budget (production parity).
                self._kill_locked()
                self._spawn_locked()
                self._await_ready_locked(deadline)
            assert self._conn is not None
            payload = {
                "observation": observation,
                "policy_manifest": policy.manifest(),
                "directives": dict(directives),
            }
            try:
                self._conn.send(("record", payload))
            except (ValueError, TypeError, AttributeError, OSError):
                self._kill_locked()
                raise WorkerFailure("unsupported_payload") from None
            wait = deadline - time.monotonic()
            if wait <= 0 or not self._conn.poll(wait):
                self._kill_locked()
                raise WorkerFailure("backend_timeout")
            try:
                kind, reply = self._conn.recv()
            except (EOFError, OSError):
                self._kill_locked()
                raise WorkerFailure("backend_crash") from None
            if kind == "err":
                # Typed in-child failure: the worker itself stays healthy.
                raise WorkerFailure(str(reply))
            if kind != "ok" or not isinstance(reply, dict):
                self._kill_locked()
                raise WorkerFailure("backend_crash")
            return reply
        finally:
            self._lock.release()

    def worker_pid(self) -> int | None:
        with self._lock:
            return self._worker_pid

    def worker_alive(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.is_alive()

    def pids_seen(self) -> list[int]:
        """Every worker pid this manager has ever spawned (evidence)."""

        with self._lock:
            return list(self._pids_seen)

    def shutdown(self) -> None:
        """Discard the current worker (bounded; safe at interpreter exit)."""

        if self._lock.acquire(timeout=_JOIN_GRACE_SECONDS):
            try:
                self._kill_locked()
            finally:
                self._lock.release()


# ---------------------------------------------------------------------------
# psutil orphan helpers (optional dependency; value-free pid sets only)
# ---------------------------------------------------------------------------


def psutil_available() -> bool:
    try:
        importlib.import_module("psutil")
    except ImportError:
        return False
    return True


def python_child_pids() -> set[int]:
    """Pids of live python descendants of this process (empty w/o psutil)."""

    try:
        psutil = importlib.import_module("psutil")
    except ImportError:
        return set()
    pids: set[int] = set()
    try:
        children = psutil.Process().children(recursive=True)
    except psutil.Error:
        return pids
    for child in children:
        try:
            if "python" in child.name().lower():
                pids.add(int(child.pid))
        except psutil.Error:
            continue
    return pids


def orphan_pids(before_pids: set[int]) -> list[int]:
    """Python descendants that appeared since ``before_pids`` and still live."""

    return sorted(python_child_pids() - set(before_pids))
