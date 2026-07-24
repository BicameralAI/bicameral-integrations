# SPDX-License-Identifier: MIT
"""Typed-failure envelope of the guarded redaction boundary (GH #260)."""

from __future__ import annotations

import pytest

from adapter.core.capabilities import SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.redaction_receipt import (
    RedactionFailure,
    guarded_sanitize_observation,
    receipt_digest,
    sanitize_observation,
)


def _observation(**overrides: object) -> Observation:
    base: dict = {
        "source_ref": SourceRef(source_id="local_directory", ref="local-abc123", kind="note"),
        "excerpt": "Decision recorded; contact ops@example.com for the runbook.",
        "mode": SourceMode.PASSIVE,
        "title": "notes",
        "timestamp": "2026-07-21T10:00:00Z",
    }
    base.update(overrides)
    return Observation(**base)  # type: ignore[arg-type]


def test_guarded_boundary_returns_receipt_and_redacts() -> None:
    sanitized, receipt = guarded_sanitize_observation(_observation())
    assert "[redacted:email]" in sanitized.excerpt
    assert receipt["schema_version"] == 1
    assert receipt["structural_fields_preserved"] is True


def test_receipt_digest_excludes_completed_at_only() -> None:
    _, first = sanitize_observation(_observation(), completed_at="2026-07-22T01:00:00Z")
    _, second = sanitize_observation(_observation(), completed_at="2026-07-22T02:00:00Z")
    assert first["completed_at"] != second["completed_at"]
    assert receipt_digest(first) == receipt_digest(second)


def test_receipt_never_contains_original_values() -> None:
    _, receipt = guarded_sanitize_observation(_observation())
    assert "ops@example.com" not in str(receipt)


def test_engine_unavailable_is_typed() -> None:
    with pytest.raises(RedactionFailure) as excinfo:
        guarded_sanitize_observation(_observation(), engine=None)
    assert excinfo.value.reason == "engine_unavailable"


def test_oversized_payload_is_typed() -> None:
    with pytest.raises(RedactionFailure) as excinfo:
        guarded_sanitize_observation(_observation(excerpt="x" * 4096), max_bytes=1024)
    assert excinfo.value.reason == "oversized_payload"


def test_unsupported_binary_metadata_is_typed() -> None:
    with pytest.raises(RedactionFailure) as excinfo:
        guarded_sanitize_observation(_observation(metadata={"blob": b"\x00"}))
    assert "unsupported" in excinfo.value.reason


def test_prohibited_identity_content_rejects_value_free() -> None:
    secret = "ghp_" + "b" * 36
    with pytest.raises(RedactionFailure) as excinfo:
        guarded_sanitize_observation(
            _observation(source_ref=SourceRef(source_id="local_directory", ref=f"local-{secret}", kind="note"))
        )
    assert excinfo.value.reason.startswith("sensitive_identity_field")
    assert secret not in str(excinfo.value)


def test_structural_identity_fields_survive_byte_identical() -> None:
    observation = _observation()
    sanitized, _ = guarded_sanitize_observation(observation)
    assert sanitized.source_ref == observation.source_ref
    assert sanitized.timestamp == observation.timestamp
    assert sanitized.provider_event_id == observation.provider_event_id
