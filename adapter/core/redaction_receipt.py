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
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import replace
from datetime import datetime, timezone

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
# One shared worker pool for bounded-timeout sanitization; sized small because
# sanitization is CPU-light and normalize() awaits each result synchronously.
_GATE_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="redaction-gate")
_GATE_BUDGET_SECONDS = 5.0


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
    - ``timeout`` — sanitization exceeded its wall-clock budget;
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

    # Bounded enforcement: the sanitizer runs on a worker thread and the
    # caller waits at most budget_seconds -- the budget is enforced BEFORE an
    # unbounded call could return, not detected afterwards. (The worker may
    # finish in the background; its result is discarded on timeout.)
    future = _GATE_EXECUTOR.submit(
        sanitize_observation, observation, completed_at=completed_at
    )
    try:
        sanitized, receipt = future.result(timeout=budget_seconds)
    except FuturesTimeout:
        future.cancel()
        raise RedactionFailure("timeout") from None

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
