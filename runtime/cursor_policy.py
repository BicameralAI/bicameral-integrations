# SPDX-License-Identifier: MIT
"""Cursor advance/quarantine policy for the operator-runtime boundary (RFQ #42, PR #69).

Codifies the Domain-3 cursor-advance table from the integrations/bot boundary
specification into a single, testable decision function.  The operator-runtime
layer calls ``resolve_cursor_action`` after each delivery attempt; the returned
``CursorAction`` tells the runtime whether to advance the watermark, retry with
backoff, or quarantine the batch and alert.

Design constraints (from #42 / PR #69):
- Cursor advance is a **two-phase commit** (emit → confirm 201 → persist).
- A crash between emit and persist → at-least-once; bot dedup expected.
- Integrations does NOT own bot dedup or event-store state.
- Terminal outcomes are recordable for operator review.
- Sensitive-data rejection is never silently advanced.
- Schema drift fails the contract gate; the cursor must not advance.

This module is stdlib-only and depends only on ``sinks.GatewayEmissionError``
for status classification.  It does NOT perform the cursor persistence itself —
that remains the operator-runtime's responsibility.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from .poll_auth import PollError
from .sinks import GatewayEmissionError


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class CursorVerdict(enum.Enum):
    """What the runtime should do with the cursor after a delivery attempt."""

    ADVANCE = "advance"
    """Advance the cursor: evidence was durably ingested (201) or terminally
    rejected in a way that re-emitting would deterministically fail again."""

    RETRY = "retry"
    """Do NOT advance; retry with backoff.  Transient failure (429, 5xx,
    transport error) — the same payload should succeed on a subsequent attempt."""

    QUARANTINE = "quarantine"
    """Do NOT advance; quarantine the batch and alert the operator.  The failure
    indicates a systemic issue (sensitive-data gap, schema drift) that cannot
    be resolved by retry alone."""


class TerminalReason(enum.Enum):
    """Classification of terminal 4xx outcomes for operator review."""

    GOVERNANCE_VETO = "governance_veto"
    """Bot policy/governance rejected the evidence (e.g. authority claim)."""

    PAYLOAD_INVALID = "payload_invalid"
    """Malformed or oversized payload that will never pass validation."""

    UNKNOWN_CLIENT_ERROR = "unknown_client_error"
    """Unclassified 4xx; recorded for operator triage."""


class QuarantineReason(enum.Enum):
    """Why a batch was quarantined (non-retryable, non-advanceable)."""

    SENSITIVE_DATA_REJECTED = "sensitive_data_rejected"
    """A sensitive-data screen rejected the emission.  Indicates a redaction
    gap — re-emit would re-fail; needs operator/connector fix."""

    SCHEMA_DRIFT = "schema_drift"
    """The envelope was rejected as malformed by the gateway schema gate.
    The mapping is stale; fix-forward, don't lose the cursor."""


@dataclass(frozen=True)
class CursorAction:
    """The resolved cursor policy decision.

    Attributes:
        verdict: What to do with the cursor.
        terminal_reason: For ADVANCE on terminal 4xx, classifies the failure
            for operator review.  ``None`` on a successful 201 advance.
        quarantine_reason: For QUARANTINE, the systemic issue class.
        status: The HTTP status code (0 for transport failures).
        detail: Free-form, token-free detail string for logging.
    """

    verdict: CursorVerdict
    terminal_reason: TerminalReason | None = None
    quarantine_reason: QuarantineReason | None = None
    status: int = 0
    detail: str = ""


# ---------------------------------------------------------------------------
# Status classification helpers
# ---------------------------------------------------------------------------

_SUCCESS_STATUS = 201
_RATE_LIMIT_STATUS = 429
_SENSITIVE_REJECTION_STATUSES = frozenset({422})
# 422 is the conventional status for a semantic validation failure (the gateway
# uses it for sensitive-data rejection per the ingest guards).  The operator
# can also signal sensitive rejection via the `reason` field.

_SENSITIVE_REASONS = frozenset(
    {
        "sensitive_data_rejected",
        "secret_detected",
        "phi_detected",
        "pan_detected",
    }
)

_SCHEMA_DRIFT_REASONS = frozenset(
    {
        "schema_invalid",
        "schema_drift",
        "envelope_malformed",
        "protocol_mismatch",
    }
)

# The GatewaySink collapses every Bot HTTP rejection body to this fixed,
# value-free reason so a token-echoing gateway response can never leak through
# the failure channel. The specific cause is deliberately not carried, so an
# opaque rejection MUST be classified fail-closed by its status alone rather
# than treated as a benign terminal 4xx that advances the cursor.
_OPAQUE_GATEWAY_REASON = "gateway_rejected"


def _is_opaque_gateway_reason(reason: str) -> bool:
    """True when the reason carries no discriminating cause.

    Covers both the empty reason and the GatewaySink's fixed token-safe
    ``gateway_rejected`` sentinel.
    """
    reason_lower = reason.lower()
    return reason_lower == "" or reason_lower == _OPAQUE_GATEWAY_REASON


def _is_sensitive_rejection(status: int, reason: str) -> bool:
    """True if the failure indicates a sensitive-data screen rejection."""
    reason_lower = reason.lower()
    if any(r in reason_lower for r in _SENSITIVE_REASONS):
        return True
    # A 422 with no discriminating reason — including the GatewaySink's opaque
    # token-safe reason — defaults to sensitive rejection: the gateway's
    # primary use of 422 is FX-SEC-001 enforcement, so the cursor must never
    # advance past a possible sensitive veto.
    if status in _SENSITIVE_REJECTION_STATUSES and _is_opaque_gateway_reason(reason):
        return True
    return False


def _is_schema_drift(status: int, reason: str) -> bool:
    """True if the failure indicates a schema/envelope conformance issue."""
    reason_lower = reason.lower()
    if any(r in reason_lower for r in _SCHEMA_DRIFT_REASONS):
        return True
    # Capability negotiation exact-matches the contract before any POST, so a
    # Bot 400 after that handshake can only mean the producer's envelope
    # mapping went stale between negotiation and delivery. The opaque token-safe
    # reason carries no discriminator, so fail closed to a schema-drift
    # quarantine (fix-forward) rather than advancing the cursor.
    if status == 400 and _is_opaque_gateway_reason(reason):
        return True
    return False


def _is_retryable_status(status: int) -> bool:
    """True for 429, 5xx, or transport failure (status=0)."""
    if status == 0:
        return True  # transport failure
    if status == _RATE_LIMIT_STATUS:
        return True
    if status >= 500:
        return True
    return False


def _classify_terminal_4xx(status: int) -> TerminalReason:
    """Classify a terminal 4xx for operator review."""
    if status == 400:
        return TerminalReason.PAYLOAD_INVALID
    if status == 403:
        return TerminalReason.GOVERNANCE_VETO
    return TerminalReason.UNKNOWN_CLIENT_ERROR


# ---------------------------------------------------------------------------
# Main policy function
# ---------------------------------------------------------------------------


def resolve_cursor_action(
    *,
    error: GatewayEmissionError | PollError | None = None,
    status: int | None = None,
    reason: str = "",
) -> CursorAction:
    """Resolve the cursor action after a delivery attempt.

    Call with ``error=None`` and ``status=201`` on success.
    Call with the caught ``GatewayEmissionError`` or ``PollError`` on failure.
    Alternatively, pass raw ``status`` + ``reason`` directly (for operator-
    runtime implementations that don't use ``GatewaySink``).

    Returns a ``CursorAction`` encoding the verdict, classification, and detail.

    Examples::

        # Successful delivery
        action = resolve_cursor_action(status=201)
        assert action.verdict == CursorVerdict.ADVANCE

        # Rate-limited
        action = resolve_cursor_action(error=GatewayEmissionError(429, "rate_limited"))
        assert action.verdict == CursorVerdict.RETRY

        # Sensitive data
        action = resolve_cursor_action(error=GatewayEmissionError(422, "sensitive_data_rejected"))
        assert action.verdict == CursorVerdict.QUARANTINE
    """
    # Derive status/reason from error if provided
    if error is not None:
        status = error.status
        reason = error.reason
    elif status is None:
        raise ValueError("Either 'error' or 'status' must be provided")

    # 1. Success (201): advance
    if status == _SUCCESS_STATUS:
        return CursorAction(
            verdict=CursorVerdict.ADVANCE,
            status=status,
            detail="evidence durably ingested",
        )

    # 2. Sensitive-data rejection: quarantine + alert (never silently advance)
    if _is_sensitive_rejection(status, reason):
        return CursorAction(
            verdict=CursorVerdict.QUARANTINE,
            quarantine_reason=QuarantineReason.SENSITIVE_DATA_REJECTED,
            status=status,
            detail=f"sensitive-data rejection ({reason or 'unspecified'}); "
            "needs operator/connector fix",
        )

    # 3. Schema drift: quarantine (mapping stale; fail contract gate)
    if _is_schema_drift(status, reason):
        return CursorAction(
            verdict=CursorVerdict.QUARANTINE,
            quarantine_reason=QuarantineReason.SCHEMA_DRIFT,
            status=status,
            detail=f"schema drift ({reason or 'unspecified'}); "
            "envelope mapping stale — fix-forward",
        )

    # 4. Retryable (429, 5xx, transport failure): do NOT advance; retry/backoff
    if _is_retryable_status(status):
        return CursorAction(
            verdict=CursorVerdict.RETRY,
            status=status,
            detail=f"transient failure (status={status}); retry with backoff",
        )

    # 5. Terminal 4xx (after bot receipt): advance + record terminal outcome
    #    Re-emitting would deterministically fail; do not wedge the poller.
    if 400 <= status < 500:
        terminal_reason = _classify_terminal_4xx(status)
        return CursorAction(
            verdict=CursorVerdict.ADVANCE,
            terminal_reason=terminal_reason,
            status=status,
            detail=f"terminal 4xx (status={status}, reason={reason or 'unknown'}); "
            "re-emit would fail deterministically",
        )

    # 6. Unexpected status: treat as retryable (conservative — do not advance)
    return CursorAction(
        verdict=CursorVerdict.RETRY,
        status=status,
        detail=f"unexpected status ({status}); treating as retryable",
    )
