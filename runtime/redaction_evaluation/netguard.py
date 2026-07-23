# SPDX-License-Identifier: MIT
"""Offline execution proof: socket-level network denial per candidate.

Each candidate is exercised in a fresh spawn-context child process whose
first action, before any backend import, is to monkeypatch
``socket.socket.connect``, ``socket.socket.connect_ex``,
``socket.create_connection``, and ``socket.getaddrinfo`` so that every
outbound attempt is recorded and denied with
``OSError("network_denied_by_evaluation")``. Everything above the socket
layer (ssl, http.client, urllib, requests, httpx) funnels through these
entry points, so patching here intercepts them all. Nothing is exempted:
loopback attempts are denied and recorded too. On Windows,
``multiprocessing`` pipes are named pipes, not sockets, so the guard does
not interfere with result delivery.
"""

from __future__ import annotations

import os
import sys
import traceback
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any

from .policy import RedactionPolicy

_OFFLINE_CHILD_ENV = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
}
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_DENIAL_MESSAGE = "network_denied_by_evaluation"
_CHILD_TIMEOUT_SECONDS = 600.0


def _sample_texts() -> tuple[str, str, str]:
    """Synthetic analyze inputs; secret-shaped tokens composed from parts."""

    email = "".join(("offline.probe", "@", "synthetic-example", ".com"))
    key_id = "".join(("AKIA", "SYNTHETICO", "FFLN01"))
    pan = " ".join(("4111", "1111", "1111", "1111"))
    return (
        "Routine sync note without sensitive content, reviewed at cadence.",
        "Contact " + email + " about rotating legacy key " + key_id + " soon.",
        "The archived card " + pan + " must never appear in sanitized output.",
    )


def _origin_module() -> str:
    """Innermost stack frame outside this module, as ``file_stem.function``."""

    for frame in reversed(traceback.extract_stack()):
        filename = frame.filename.replace("\\", "/")
        if filename.endswith("/netguard.py"):
            continue
        return f"{Path(filename).stem}.{frame.name}"
    return "unknown"


def _split_address(address: object) -> tuple[str, object]:
    if isinstance(address, tuple) and len(address) >= 2:
        return str(address[0]), address[1]
    return str(address), None


def _install_socket_guard(attempts: list[dict[str, Any]]) -> None:
    """Deny and record every connection attempt at the socket layer."""

    import socket

    def _record_and_deny(address: object) -> None:
        host, port = _split_address(address)
        attempts.append(
            {"host": host, "port": port, "origin_module": _origin_module()}
        )
        raise OSError(_DENIAL_MESSAGE)

    def guarded_connect(
        self: socket.socket, address: object, *args: Any, **kwargs: Any
    ) -> None:
        del self, args, kwargs
        _record_and_deny(address)

    def guarded_connect_ex(
        self: socket.socket, address: object, *args: Any, **kwargs: Any
    ) -> int:
        del self, args, kwargs
        _record_and_deny(address)
        return -1  # unreachable; _record_and_deny always raises

    def guarded_create_connection(
        address: object, *args: Any, **kwargs: Any
    ) -> Any:
        del args, kwargs
        _record_and_deny(address)

    def guarded_getaddrinfo(
        host: object, port: object, *args: Any, **kwargs: Any
    ) -> Any:
        del args, kwargs
        _record_and_deny((host, port))

    socket.socket.connect = guarded_connect  # type: ignore[assignment, method-assign]
    socket.socket.connect_ex = guarded_connect_ex  # type: ignore[assignment, method-assign]
    socket.create_connection = guarded_create_connection  # type: ignore[assignment]
    socket.getaddrinfo = guarded_getaddrinfo  # type: ignore[assignment]


def _offline_child(
    candidate_id: str, policy: RedactionPolicy | None, conn: Connection
) -> None:
    """Child body: env pins, then guard install, then backend exercise."""

    for key, value in _OFFLINE_CHILD_ENV.items():
        os.environ[key] = value
    attempts: list[dict[str, Any]] = []
    _install_socket_guard(attempts)
    result: dict[str, Any] = {
        "candidate_id": candidate_id,
        "initialized": False,
        "analyze_ok": False,
        "error": None,
    }
    try:
        from .backends import create_backend

        active_policy = policy if policy is not None else RedactionPolicy()
        backend = create_backend(candidate_id)
        backend.initialize()
        result["initialized"] = True
        for text in _sample_texts():
            backend.analyze(text, field_path="excerpt", policy=active_policy)
        result["analyze_ok"] = True
    except BaseException as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["attempted_connections"] = [
        attempt for attempt in attempts if attempt["host"] not in _LOOPBACK_HOSTS
    ]
    result["loopback_attempts"] = [
        attempt for attempt in attempts if attempt["host"] in _LOOPBACK_HOSTS
    ]
    conn.send(result)
    conn.close()


def offline_proof(
    candidate_ids: list[str],
    *,
    repo_root: Path,
    policy: RedactionPolicy | None = None,
) -> dict[str, Any]:
    """Prove each candidate initializes and analyzes with networking denied.

    Gate rule: a candidate passes only if it (a) initializes and analyzes
    successfully with the socket guard installed, (b) records no
    non-loopback connection attempt, and (c) did not fail because of the
    network denial. DNS/getaddrinfo lookups for loopback hosts can be
    triggered innocuously by library imports; those are still denied and
    recorded, but they are classified separately under
    ``loopback_attempts`` and do not fail the gate by themselves. Any
    NON-loopback attempt fails the gate regardless of analyze outcome, and
    a loopback denial that breaks initialization or analysis also fails
    the gate (surfaced via ``network_denial_caused_failure``).

    Must be called from a ``__main__``-guarded script: children use the
    multiprocessing spawn context.
    """

    import multiprocessing

    repo_root = Path(repo_root)
    entry = str(repo_root)
    if entry not in sys.path:
        sys.path.insert(0, entry)
    ctx = multiprocessing.get_context("spawn")
    candidates: list[dict[str, Any]] = []
    previous_env = {key: os.environ.get(key) for key in _OFFLINE_CHILD_ENV}
    os.environ.update(_OFFLINE_CHILD_ENV)
    try:
        for candidate_id in candidate_ids:
            parent_conn, child_conn = ctx.Pipe(duplex=False)
            proc = ctx.Process(
                target=_offline_child, args=(candidate_id, policy, child_conn)
            )
            proc.start()
            child_conn.close()
            result: dict[str, Any]
            if parent_conn.poll(_CHILD_TIMEOUT_SECONDS):
                try:
                    result = parent_conn.recv()
                except EOFError:
                    result = {
                        "candidate_id": candidate_id,
                        "initialized": False,
                        "analyze_ok": False,
                        "attempted_connections": [],
                        "loopback_attempts": [],
                        "error": "offline_child_died_without_result",
                    }
            else:
                result = {
                    "candidate_id": candidate_id,
                    "initialized": False,
                    "analyze_ok": False,
                    "attempted_connections": [],
                    "loopback_attempts": [],
                    "error": "offline_child_timeout",
                }
            proc.join(30.0)
            if proc.is_alive():
                proc.terminate()
                proc.join(10.0)
                if proc.is_alive():
                    proc.kill()
                    proc.join(10.0)
            parent_conn.close()
            error = result.get("error")
            denial_caused_failure = bool(error) and _DENIAL_MESSAGE in str(error)
            result["network_denial_caused_failure"] = denial_caused_failure
            result["passed"] = (
                result.get("initialized") is True
                and result.get("analyze_ok") is True
                and not result.get("attempted_connections")
                and not denial_caused_failure
            )
            candidates.append(result)
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return {
        "schema_version": 1,
        "proof": "socket-deny",
        "candidates": candidates,
        "generated_by": "scripts/evaluate_redaction_backends.py",
    }
