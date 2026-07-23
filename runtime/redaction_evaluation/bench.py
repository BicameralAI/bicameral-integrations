# SPDX-License-Identifier: MIT
"""Performance benchmark harness for one redaction backend candidate.

Implements the ADR-0020 performance contract on one documented host:
cold initialization is measured only in separate spawned interpreters and is
never blended with warm numbers; warm latency, throughput, peak memory, CPU,
concurrency, worker startup, and timeout recovery are measured in-process or
in dedicated child processes. Payloads are synthetic, deterministic, and
built in-code; secret-shaped tokens are composed from concatenated parts so
no complete credential-shaped literal appears in the source tree.

Callers using the multiprocessing-backed measurements (worker startup,
timeout recovery) must invoke this module from a script guarded by
``if __name__ == "__main__"`` because child processes use the spawn context.
The cold-initialization child uses the caller-independent default policy;
warm measurements use the policy passed by the caller.
"""

from __future__ import annotations

import json
import math
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any

from .inventory import (
    directory_size_bytes,
    distribution_files_bytes,
    hf_cache_dir,
    resolve_distribution,
)
from .policy import RedactionPolicy
from .seam import RedactionBackend

_OFFLINE_ENV = {
    "HF_HUB_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
}
_WARMUP_CALLS = 20
_SAMPLE_INTERVAL_SECONDS = 0.05
_HANG_BUDGET_SECONDS = 1.0
_PAYLOAD_CLASS_ORDER = ("small", "medium", "large", "max_admitted")
_PAYLOAD_TARGET_CHARS = {"small": 200, "medium": 2_000, "large": 20_000}
_MAX_ADMITTED_MARGIN_BYTES = 4_096

_CLEAN_SENTENCES = (
    "The ingestion pipeline batches provider events into observation records. ",
    "Deterministic replacement keeps sanitized output byte-stable across runs. ",
    "Cursor state advances only after the sanitized record is durably written. ",
    "Connector health is reported through value-free readiness signals. ",
    "The evaluation corpus is synthetic and contains no real customer data. ",
)


def _synthetic_email() -> str:
    return "".join(("eval.user", "@", "synthetic-example", ".com"))


def _synthetic_phone() -> str:
    return "".join(("(", "555", ") ", "014", "-", "2323"))


def _synthetic_pan() -> str:
    return " ".join(("4111", "1111", "1111", "1111"))


def _synthetic_key_id() -> str:
    return "".join(("AKIA", "SYNTHETICB", "ENCH01"))


def _pii_sentences() -> tuple[str, ...]:
    return (
        "Contact " + _synthetic_email() + " for rotation approval. ",
        "Call " + _synthetic_phone() + " before the maintenance window. ",
        "Card on file " + _synthetic_pan() + " is scheduled for archival. ",
        "Legacy key " + _synthetic_key_id() + " awaits revocation. ",
    )


def _build_text(target_chars: int) -> str:
    """Deterministic synthetic text mixing clean and PII-shaped sentences."""

    pii = _pii_sentences()
    parts: list[str] = []
    total = 0
    index = 0
    while total < target_chars:
        sentence = _CLEAN_SENTENCES[index % len(_CLEAN_SENTENCES)]
        parts.append(sentence)
        total += len(sentence)
        if index % 3 == 2:
            token_sentence = pii[(index // 3) % len(pii)]
            parts.append(token_sentence)
            total += len(token_sentence)
        index += 1
    return "".join(parts)[:target_chars]


def _observation_document(text: str) -> dict[str, Any]:
    """Synthetic observation envelope mirroring the admitted-field layout."""

    return {
        "evidence_id": "bench-evidence-0001",
        "timestamp": "2026-01-01T00:00:00Z",
        "provider_event_id": "bench-event-0001",
        "provider_resource_id": "bench-resource-0001",
        "source_ref": {
            "source_id": "bench-source",
            "ref": "bench/ref",
            "url": "",
            "kind": "synthetic",
        },
        "title": "Synthetic benchmark record",
        "author": "Benchmark Harness",
        "excerpt": text,
        "evidence_metadata": {},
        "metadata": {},
    }


def _serialized_observation_bytes(text: str) -> int:
    encoded = json.dumps(
        _observation_document(text), ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")
    return len(encoded)


def build_payloads(policy: RedactionPolicy) -> dict[str, str]:
    """Deterministic payload classes: small, medium, large, max_admitted."""

    overhead = _serialized_observation_bytes("")
    max_chars = policy.max_payload_bytes - overhead - _MAX_ADMITTED_MARGIN_BYTES
    if max_chars <= 0:
        raise ValueError("policy.max_payload_bytes too small for the envelope")
    payloads = {
        name: _build_text(chars) for name, chars in _PAYLOAD_TARGET_CHARS.items()
    }
    payloads["max_admitted"] = _build_text(max_chars)
    if _serialized_observation_bytes(payloads["max_admitted"]) >= (
        policy.max_payload_bytes
    ):
        raise ValueError("max_admitted payload breaches policy.max_payload_bytes")
    return payloads


def _ensure_repo_on_path(repo_root: Path) -> None:
    entry = str(repo_root)
    if entry not in sys.path:
        sys.path.insert(0, entry)


@contextmanager
def _offline_env() -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in _OFFLINE_ENV}
    os.environ.update(_OFFLINE_ENV)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _percentile(sorted_values: list[float], quantile: float) -> float:
    """Nearest-rank percentile over an ascending list (numpy-free)."""

    if not sorted_values:
        return 0.0
    rank = max(1, math.ceil(quantile / 100.0 * len(sorted_values)))
    return sorted_values[min(rank, len(sorted_values)) - 1]


class _PeakRssSampler:
    """Background 50 ms RSS sampler; fallback when peak_wset is unavailable."""

    def __init__(
        self, process: Any, interval_seconds: float = _SAMPLE_INTERVAL_SECONDS
    ) -> None:
        self._process = process
        self._interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._peak_bytes = 0
        self._thread = threading.Thread(
            target=self._run, name="bench-rss-sampler", daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> int:
        self._stop_event.set()
        self._thread.join(timeout=5.0)
        return self._peak_bytes

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                rss = int(self._process.memory_info().rss)
            except Exception:
                break
            self._peak_bytes = max(self._peak_bytes, rss)
            self._stop_event.wait(self._interval_seconds)


_COLD_CHILD_TEMPLATE = """\
import json, time
t0 = time.perf_counter()
from runtime.redaction_evaluation.backends import create_backend
from runtime.redaction_evaluation.policy import RedactionPolicy
backend = create_backend({candidate_id!r})
backend.initialize()
backend.analyze({text!r}, field_path="excerpt", policy=RedactionPolicy())
print(json.dumps({{"cold_seconds": time.perf_counter() - t0}}))
"""


def _measure_cold_initialization(
    candidate_id: str, repo_root: Path, small_text: str, cold_runs: int
) -> dict[str, Any]:
    """Cold init in separate interpreters; the only cold measurement site."""

    program = _COLD_CHILD_TEMPLATE.format(candidate_id=candidate_id, text=small_text)
    env = {**os.environ, **_OFFLINE_ENV}
    runs: list[float] = []
    for _ in range(cold_runs):
        completed = subprocess.run(
            [sys.executable, "-c", program],
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "cold_init_child_failed: " + completed.stderr.strip()[-2000:]
            )
        last_line = completed.stdout.strip().splitlines()[-1]
        runs.append(float(json.loads(last_line)["cold_seconds"]))
    return {
        "runs": cold_runs,
        "runs_seconds": runs,
        "median_seconds": statistics.median(runs),
        "measurement_basis": (
            "wall time inside a fresh spawned interpreter (cwd=repo root, HF "
            "offline env) covering backend import + create_backend + "
            "initialize + one small-payload analyze under the default "
            "policy; interpreter startup itself is reported separately as "
            "worker_startup_seconds"
        ),
    }


def _worker_ready_child(candidate_id: str, conn: Connection) -> None:
    from runtime.redaction_evaluation.backends import create_backend

    create_backend(candidate_id)
    conn.send("ready")
    conn.close()


def _measure_worker_startup(candidate_id: str, runs: int = 3) -> dict[str, Any]:
    import multiprocessing

    ctx = multiprocessing.get_context("spawn")
    samples: list[float] = []
    for _ in range(runs):
        parent_conn, child_conn = ctx.Pipe(duplex=False)
        started = time.perf_counter()
        proc = ctx.Process(
            target=_worker_ready_child, args=(candidate_id, child_conn)
        )
        proc.start()
        child_conn.close()
        if not parent_conn.poll(300):
            proc.terminate()
            proc.join(10.0)
            parent_conn.close()
            raise RuntimeError("worker_startup_child_unresponsive")
        try:
            parent_conn.recv()
        except EOFError as exc:
            proc.join(10.0)
            parent_conn.close()
            raise RuntimeError("worker_startup_child_died") from exc
        samples.append(time.perf_counter() - started)
        proc.join(30.0)
        parent_conn.close()
    return {
        "runs_seconds": samples,
        "median_seconds": statistics.median(samples),
        "measurement_basis": (
            "spawn-context interpreter start + backend module import + "
            "backend construction until a ready message arrives on a pipe"
        ),
    }


def _hang_child(candidate_id: str, budget_seconds: float, conn: Connection) -> None:
    from runtime.redaction_evaluation.backends import create_backend
    from runtime.redaction_evaluation.backends.faults import FaultInjectedBackend

    base = create_backend(candidate_id)
    backend = FaultInjectedBackend(base.identity, "hang")
    policy = replace(RedactionPolicy(), per_record_budget_seconds=budget_seconds)
    conn.send("analyzing")
    backend.analyze("synthetic hang probe", field_path="excerpt", policy=policy)


def _measure_timeout_recovery(candidate_id: str, runs: int = 3) -> dict[str, Any]:
    import multiprocessing

    import psutil  # type: ignore[import-not-found, import-untyped]

    ctx = multiprocessing.get_context("spawn")
    samples: list[float] = []
    errors: list[str] = []
    orphan_count = 0
    for _ in range(runs):
        parent_conn, child_conn = ctx.Pipe(duplex=False)
        proc = ctx.Process(
            target=_hang_child, args=(candidate_id, _HANG_BUDGET_SECONDS, child_conn)
        )
        proc.start()
        child_conn.close()
        signaled = parent_conn.poll(120)
        if signaled:
            try:
                parent_conn.recv()
            except EOFError:
                signaled = False
        if not signaled:
            errors.append("hang_child_never_signaled")
            proc.terminate()
            proc.join(10.0)
            parent_conn.close()
            continue
        time.sleep(_HANG_BUDGET_SECONDS)
        descendant_pids: list[int] = []
        try:
            descendant_pids = [
                child.pid
                for child in psutil.Process(proc.pid).children(recursive=True)
            ]
        except psutil.Error:
            pass
        expiry = time.perf_counter()
        proc.terminate()
        proc.join(5.0)
        if proc.is_alive():
            proc.kill()
            proc.join(5.0)
        samples.append(time.perf_counter() - expiry)
        if proc.is_alive():
            orphan_count += 1
        for pid in descendant_pids:
            if psutil.pid_exists(pid):
                orphan_count += 1
        parent_conn.close()
    return {
        "runs_seconds": samples,
        "median_seconds": statistics.median(samples) if samples else None,
        "orphan_count": orphan_count,
        "simulated_budget_seconds": _HANG_BUDGET_SECONDS,
        "errors": errors,
        "measurement_basis": (
            "time from simulated budget expiry to confirmed termination "
            "(terminate -> join -> kill -> join) of a spawn-context worker "
            "running the hang fault; orphans = worker or descendant pids "
            "still alive afterwards per psutil"
        ),
    }


def _measure_concurrency(
    backend: RedactionBackend,
    text: str,
    policy: RedactionPolicy,
    serial_expectation_seconds: float,
) -> dict[str, Any]:
    errors: list[str] = []
    errors_lock = threading.Lock()

    def worker() -> None:
        for _ in range(25):
            try:
                backend.analyze(text, field_path="excerpt", policy=policy)
            except Exception as exc:
                with errors_lock:
                    errors.append(type(exc).__name__)
                return

    threads = [threading.Thread(target=worker) for _ in range(4)]
    started = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    wall_seconds = time.perf_counter() - started
    doc: dict[str, Any] = {
        "threads": 4,
        "calls_per_thread": 25,
        "payload_class": "medium",
        "wall_seconds": wall_seconds,
        "serial_expectation_seconds": serial_expectation_seconds,
        "speedup_factor": (
            serial_expectation_seconds / wall_seconds if wall_seconds > 0 else None
        ),
        "thread_safe": not errors,
    }
    if errors:
        doc["error_type"] = errors[0]
    return doc


def _measure_package_bytes(identity: Any) -> dict[str, Any]:
    packages: dict[str, Any] = {}
    total = 0
    for name in sorted(identity.packages):
        declared_version = identity.packages[name]
        dist = resolve_distribution(name)
        if dist is None:
            packages[name] = {
                "bytes": None,
                "declared_version": declared_version,
                "basis": "unresolved-in-venv",
            }
            continue
        size = distribution_files_bytes(dist)
        packages[name] = {
            "bytes": size,
            "declared_version": declared_version,
            "installed_version": dist.version,
            "basis": "importlib.metadata file-size sum",
        }
        if isinstance(size, int):
            total += size
    return {
        "packages": packages,
        "total_bytes": total,
        "measurement_basis": (
            "sum of importlib.metadata recorded file sizes for each "
            "resolvable declared package in the evaluation venv"
        ),
    }


def _locate_model(name: str, reference: str) -> dict[str, Any]:
    for candidate_name in (name, reference):
        if not candidate_name:
            continue
        dist = resolve_distribution(candidate_name)
        if dist is not None:
            return {
                "bytes": distribution_files_bytes(dist),
                "path": None,
                "installed_version": dist.version,
                "basis": "installed-distribution-files",
            }
    cache = hf_cache_dir()
    if cache is not None and cache.exists():
        needles = {
            candidate_name.split("/")[-1].lower()
            for candidate_name in (name, reference)
            if candidate_name
        }
        for child in sorted(cache.iterdir(), key=lambda p: p.name):
            if not child.is_dir():
                continue
            lowered = child.name.lower()
            if any(needle in lowered for needle in needles):
                return {
                    "bytes": directory_size_bytes(child),
                    "path": str(child),
                    "basis": "hf-cache-model-directory (blobs + snapshots)",
                }
    return {"bytes": None, "path": None, "basis": "not-found"}


def _measure_model_bytes(identity: Any) -> dict[str, Any]:
    models: dict[str, Any] = {}
    total = 0
    for name in sorted(identity.models):
        entry = _locate_model(name, str(identity.models[name]))
        models[name] = entry
        if isinstance(entry.get("bytes"), int):
            total += entry["bytes"]
    return {
        "models": models,
        "total_bytes": total,
        "measurement_basis": (
            "best-effort: installed distribution file sizes when the model "
            "ships as a package, else a Hugging Face cache directory scan "
            "matched on the declared model name"
        ),
    }


def _environment_doc(psutil_module: Any) -> dict[str, Any]:
    cpu_freq: dict[str, float] | None = None
    try:
        freq = psutil_module.cpu_freq()
        if freq is not None:
            cpu_freq = {"current_mhz": freq.current, "max_mhz": freq.max}
    except Exception:
        cpu_freq = None
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "cpu_freq": cpu_freq,
    }


def run_benchmarks(
    candidate_id: str,
    *,
    repo_root: Path,
    policy: RedactionPolicy | None = None,
    warm_iterations: int = 200,
    cold_runs: int = 3,
) -> dict[str, Any]:
    """Run the full performance contract for one candidate.

    Returns a JSON-serializable document. Cold initialization runs in
    ``cold_runs`` separate spawned interpreters and is never blended with
    the warm measurements taken in-process afterwards.
    """

    if warm_iterations < 1 or cold_runs < 1:
        raise ValueError("warm_iterations and cold_runs must be >= 1")
    import psutil  # type: ignore[import-not-found, import-untyped]

    from .backends import create_backend

    repo_root = Path(repo_root)
    _ensure_repo_on_path(repo_root)
    active_policy = policy if policy is not None else RedactionPolicy()
    payloads = build_payloads(active_policy)
    payload_doc = {
        name: {
            "chars": len(payloads[name]),
            "serialized_observation_bytes": _serialized_observation_bytes(
                payloads[name]
            ),
        }
        for name in _PAYLOAD_CLASS_ORDER
    }

    cold = _measure_cold_initialization(
        candidate_id, repo_root, payloads["small"], cold_runs
    )

    with _offline_env():
        backend = create_backend(candidate_id)
        backend.initialize()
        process = psutil.Process()
        sampler = _PeakRssSampler(process)
        sampler.start()
        warm_latency: dict[str, Any] = {}
        throughput_rps = 0.0
        medium_total_seconds = 0.0
        cpu_percent_avg: float | None = None
        try:
            for class_name in _PAYLOAD_CLASS_ORDER:
                text = payloads[class_name]
                for _ in range(_WARMUP_CALLS):
                    backend.analyze(text, field_path="excerpt", policy=active_policy)
                if class_name == "medium":
                    process.cpu_percent(None)
                durations: list[float] = []
                loop_started = time.perf_counter()
                for _ in range(warm_iterations):
                    call_started = time.perf_counter()
                    backend.analyze(text, field_path="excerpt", policy=active_policy)
                    durations.append(time.perf_counter() - call_started)
                loop_seconds = time.perf_counter() - loop_started
                if class_name == "medium":
                    cpu_percent_avg = float(process.cpu_percent(None))
                    medium_total_seconds = loop_seconds
                    throughput_rps = warm_iterations / loop_seconds
                ascending = sorted(durations)
                warm_latency[class_name] = {
                    "p50": _percentile(ascending, 50.0) * 1000.0,
                    "p95": _percentile(ascending, 95.0) * 1000.0,
                    "p99": _percentile(ascending, 99.0) * 1000.0,
                    "iterations": warm_iterations,
                }
            serial_expectation = (medium_total_seconds / warm_iterations) * 100.0
            concurrency = _measure_concurrency(
                backend, payloads["medium"], active_policy, serial_expectation
            )
        finally:
            sampled_peak = sampler.stop()
        memory = process.memory_info()
        peak_wset = getattr(memory, "peak_wset", None)
        if isinstance(peak_wset, int) and peak_wset > 0:
            peak_rss_bytes = peak_wset
            peak_rss_basis = (
                "psutil memory_info().peak_wset (Windows peak working set "
                "over the process lifetime)"
            )
        else:
            peak_rss_bytes = sampled_peak
            peak_rss_basis = (
                "maximum rss sampled every 50 ms on a background thread "
                "during the warm loops"
            )
        worker_startup = _measure_worker_startup(candidate_id)
        timeout_recovery = _measure_timeout_recovery(candidate_id)

    identity = backend.identity
    return {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "environment": _environment_doc(psutil),
        "payload_classes": payload_doc,
        "cold_initialization": cold,
        "warm_latency_ms": warm_latency,
        "throughput_rps": throughput_rps,
        "peak_rss_bytes": peak_rss_bytes,
        "peak_rss_measurement_basis": peak_rss_basis,
        "worker_startup_seconds": worker_startup,
        "package_bytes": _measure_package_bytes(identity),
        "model_bytes": _measure_model_bytes(identity),
        "cpu_percent_avg": cpu_percent_avg,
        "cpu_percent_measurement_basis": (
            "psutil Process.cpu_percent delta spanning the medium-class warm "
            "loop; can exceed 100 on multi-core hosts"
        ),
        "concurrency": concurrency,
        "timeout_recovery": timeout_recovery,
    }
