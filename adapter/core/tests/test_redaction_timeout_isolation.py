# SPDX-License-Identifier: MIT
"""Timeout isolation for the guarded redaction boundary (GH #269 round 3).

The timeout must be backed by real termination: a stuck sanitizer worker is
hard-killed and recycled, repeated timeouts cannot starve a later healthy
request, no timed-out work can mutate shared state afterwards, and no raw
sensitive value crosses the worker boundary in failure output.
"""

from __future__ import annotations

import os

import pytest

from adapter.core.capabilities import SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.redaction_receipt import (
    _WORKER,
    RedactionFailure,
    guarded_sanitize_observation,
)

_SENSITIVE = "carol@example.com"


def _observation(marker: str = "one") -> Observation:
    return Observation(
        source_ref=SourceRef(source_id="local_directory", ref=f"local-{marker}", kind="note"),
        excerpt=f"Decision {marker}; contact {_SENSITIVE} for access.",
        mode=SourceMode.PASSIVE,
        title=marker,
        timestamp="2026-07-21T10:00:00Z",
    )


@pytest.fixture()
def hung_worker(monkeypatch: pytest.MonkeyPatch):
    """Force the NEXT worker spawn to hang inside the child (test seam)."""
    monkeypatch.setenv("BICAMERAL_REDACTION_TEST_SLEEP_S", "30")
    _WORKER.reset_for_tests()
    yield
    monkeypatch.delenv("BICAMERAL_REDACTION_TEST_SLEEP_S", raising=False)
    _WORKER.reset_for_tests()


def test_timed_out_request_fails_closed_and_value_free(hung_worker: None) -> None:
    with pytest.raises(RedactionFailure) as excinfo:
        guarded_sanitize_observation(_observation(), budget_seconds=0.5)
    assert excinfo.value.reason == "timeout"
    assert _SENSITIVE not in str(excinfo.value)
    # The stuck worker was hard-terminated, not abandoned.
    assert not _WORKER.worker_alive()


def test_more_timeouts_than_any_pool_size_then_healthy_request_recovers(
    hung_worker: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Six consecutive timeouts (more than the previous 4-worker pool could
    # have absorbed) must not accumulate occupied workers...
    for index in range(6):
        with pytest.raises(RedactionFailure) as excinfo:
            guarded_sanitize_observation(_observation(f"hang-{index}"), budget_seconds=0.3)
        assert excinfo.value.reason == "timeout"
        assert not _WORKER.worker_alive()

    # ...and a later healthy request must still complete: clear the hang hook
    # and let the manager spawn a fresh, healthy worker.
    monkeypatch.delenv("BICAMERAL_REDACTION_TEST_SLEEP_S", raising=False)
    _WORKER.reset_for_tests()
    sanitized, receipt = guarded_sanitize_observation(_observation("healthy"))
    assert "[redacted:email]" in sanitized.excerpt
    assert receipt["structural_fields_preserved"] is True


def test_timed_out_work_cannot_mutate_later_results(hung_worker: None, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(RedactionFailure):
        guarded_sanitize_observation(_observation("doomed"), budget_seconds=0.3)
    monkeypatch.delenv("BICAMERAL_REDACTION_TEST_SLEEP_S", raising=False)
    _WORKER.reset_for_tests()
    # The killed worker's partial state died with its process: the healthy
    # result reflects ONLY the healthy input.
    sanitized, receipt = guarded_sanitize_observation(_observation("clean"))
    assert "clean" in sanitized.title
    assert "doomed" not in str(receipt)


def test_worker_resources_are_reclaimed_after_timeout_and_reuse() -> None:
    _WORKER.reset_for_tests()
    sanitized, _ = guarded_sanitize_observation(_observation("first"))
    assert "[redacted:email]" in sanitized.excerpt
    assert _WORKER.worker_alive()  # exactly one healthy resident worker
    _WORKER.reset_for_tests()
    assert not _WORKER.worker_alive()  # deterministic cleanup


def test_unpicklable_content_is_typed_unsupported_payload() -> None:
    _WORKER.reset_for_tests()
    observation = _observation("unpicklable")
    broken = Observation(
        source_ref=observation.source_ref,
        excerpt=observation.excerpt,
        mode=observation.mode,
        title=observation.title,
        timestamp=observation.timestamp,
        metadata={"hook": lambda: None},
    )
    with pytest.raises(RedactionFailure) as excinfo:
        guarded_sanitize_observation(broken)
    # Rejected before the worker boundary by the canonicalization guard.
    assert excinfo.value.reason.startswith("unsupported")


def test_env_hook_is_inert_without_explicit_reset() -> None:
    """The test seam requires an explicit worker reset; setting the env var
    alone cannot affect an already-running production worker."""
    _WORKER.reset_for_tests()
    guarded_sanitize_observation(_observation("warm"))
    os.environ["BICAMERAL_REDACTION_TEST_SLEEP_S"] = "30"
    try:
        sanitized, _ = guarded_sanitize_observation(_observation("still-fast"), budget_seconds=1.0)
        assert "[redacted:email]" in sanitized.excerpt
    finally:
        del os.environ["BICAMERAL_REDACTION_TEST_SLEEP_S"]
        _WORKER.reset_for_tests()
