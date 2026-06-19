"""Map a connector ``Observation`` to the SDK ``Evidence`` contract (bicameral-sdk #7).

The integrations-side of GH #187: a connector produces **non-authoritative raw evidence**,
and this seam shapes it to the SDK contract the bot consumes. Pinned against
``bicameral-sdk/src/evidence/index.ts`` + ``provenance/index.ts`` (GH #7, CLOSED) —
``SDK_EVIDENCE_CONTRACT`` records the pin; the golden fixtures in
``tests/test_sdk_evidence.py`` are the conformance lock (integrations fails first on drift).

Two invariants from the SDK contract are enforced here, not assumed:

- **``status`` is ALWAYS ``"raw"``.** "Evidence is NEVER canonical. Only reviewed and
  promoted decisions reach canonical authority." Candidate-extraction and promotion are
  downstream (bot #481/#484) — a connector must never pre-judge a candidate (SG-2026-06-18-D).
- **The capturer is the connector** (``actorType="connector"``), carrying the source id,
  never the human actor (PII never surfaced; ADR-0008 / SG-2026-06-11-D).

FX-SEC-001 parity: the mapped excerpt + string leaves are screened with
``sensitive.detect_sensitive`` before the dict is returned — a secret never leaves the edge.
Pure + stdlib-only; the operator runtime injects ``captured_at`` (the adapter holds no clock).
"""

from __future__ import annotations

import hashlib

from .observations import Observation
from .provenance import ActorType, Attribution, Provenance
from .sensitive import detect_sensitive

# Pin to the SDK contract this mapping targets (cross-repo read; integrations owns the pin).
SDK_EVIDENCE_CONTRACT = "bicameral-sdk/src/evidence/index.ts@GH#7"

_RAW = "raw"


class EvidenceExportError(ValueError):
    """Raised when a mapped evidence dict would carry sensitive data (FX-SEC-001 parity)."""


def _source_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _screen(*values: str) -> None:
    """Reject if any value carries a secret/PHI/PAN — the export must never leak (uses the
    redacted match excerpt in the error, never the raw value)."""
    for value in values:
        hits = detect_sensitive(value)
        if hits:
            raise EvidenceExportError(
                f"sensitive_data:{hits[0].cls} (pattern={hits[0].pattern_id}, "
                f"excerpt={hits[0].match_excerpt!r})"
            )


def to_sdk_evidence(
    obs: Observation, *, adapter_version: str, captured_at: str | None = None
) -> dict:
    """One connector ``Observation`` → an SDK-conformant ``Evidence`` dict (``status='raw'``).

    ``captured_at`` defaults to the observation timestamp (the operator runtime may inject the
    true ingestion time). ``capturedBy`` is the connector, never the source's human actor.
    """
    ref = obs.source_ref
    when = captured_at if captured_at is not None else obs.timestamp
    method = str(getattr(obs.mode, "value", obs.mode))  # SourceMode enum → its value; tolerate a raw str
    _screen(obs.excerpt, ref.source_id, ref.ref, ref.url, ref.kind)
    provenance = Provenance(
        captured_at=when,
        captured_by=Attribution(actor_id=ref.source_id, actor_type=ActorType.CONNECTOR),
        capture_method=method,
        pipeline_version=adapter_version,
        source_hash=_source_hash(obs.excerpt),
    )
    return {
        "id": ref.ref or provenance.source_hash,
        "source": {
            "system": ref.source_id,
            "resourceId": ref.ref,
            "resourceType": ref.kind,
            "url": ref.url,
        },
        "excerpt": {"excerpt": obs.excerpt, "capturedAt": when},
        "provenance": {
            "capturedAt": provenance.captured_at,
            "capturedBy": {
                "actorId": provenance.captured_by.actor_id,
                "actorType": provenance.captured_by.actor_type.value,
            },
            "captureMethod": provenance.capture_method,
            "pipelineVersion": provenance.pipeline_version,
            "sourceHash": provenance.source_hash,
        },
        "status": _RAW,
        "capturedAt": when,
    }


__all__ = ["SDK_EVIDENCE_CONTRACT", "EvidenceExportError", "to_sdk_evidence"]
