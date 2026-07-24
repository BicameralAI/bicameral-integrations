# SPDX-License-Identifier: MIT
"""Tests for the cursor advance/quarantine policy (issue #199, RFQ #42, PR #69).

Covers every row in the Domain-3 cursor-advance table:
- 201: advance
- Terminal 4xx after bot receipt: advance or quarantine by error class
- 429, 5xx, transport failure: do not advance; retry/backoff
- Sensitive-data rejection: do not silently advance; hold/quarantine and alert
- Schema drift: do not advance; fail contract gate
- Crash between emit and cursor persist: at-least-once, bot dedup expected

The policy does not require integrations to own bot dedup or event-store state.
Terminal outcomes are recordable for operator review.
"""

from __future__ import annotations

import pytest

from runtime.cursor_policy import (
    CursorVerdict,
    QuarantineReason,
    TerminalReason,
    resolve_cursor_action,
)
from runtime.poll_auth import PollError
from runtime.sinks import GatewayEmissionError


# ---------------------------------------------------------------------------
# 201 — advance
# ---------------------------------------------------------------------------


class TestSuccessAdvance:
    """Gateway 201 → cursor advances (evidence durably ingested)."""

    def test_status_201_advances(self) -> None:
        action = resolve_cursor_action(status=201)
        assert action.verdict == CursorVerdict.ADVANCE
        assert action.terminal_reason is None
        assert action.quarantine_reason is None
        assert action.status == 201

    def test_status_201_via_no_error(self) -> None:
        """The success path: error=None, status=201."""
        action = resolve_cursor_action(error=None, status=201)
        assert action.verdict == CursorVerdict.ADVANCE


# ---------------------------------------------------------------------------
# Terminal 4xx — advance + record terminal outcome
# ---------------------------------------------------------------------------


class TestTerminal4xx:
    """Terminal 4xx after bot receipt: advance (re-emit would deterministically fail)."""

    def test_400_payload_invalid(self) -> None:
        action = resolve_cursor_action(
            error=GatewayEmissionError(400, "payload_too_large")
        )
        assert action.verdict == CursorVerdict.ADVANCE
        assert action.terminal_reason == TerminalReason.PAYLOAD_INVALID
        assert action.status == 400

    def test_403_governance_veto(self) -> None:
        action = resolve_cursor_action(
            error=GatewayEmissionError(403, "authority_claim_rejected")
        )
        assert action.verdict == CursorVerdict.ADVANCE
        assert action.terminal_reason == TerminalReason.GOVERNANCE_VETO
        assert action.status == 403

    def test_404_unknown_client_error(self) -> None:
        action = resolve_cursor_action(error=GatewayEmissionError(404, "not_found"))
        assert action.verdict == CursorVerdict.ADVANCE
        assert action.terminal_reason == TerminalReason.UNKNOWN_CLIENT_ERROR
        assert action.status == 404

    def test_409_conflict_advances(self) -> None:
        """409 Conflict is terminal (e.g. duplicate evidence already ingested)."""
        action = resolve_cursor_action(status=409, reason="conflict")
        assert action.verdict == CursorVerdict.ADVANCE
        assert action.terminal_reason == TerminalReason.UNKNOWN_CLIENT_ERROR

    def test_terminal_outcome_recordable(self) -> None:
        """Terminal actions carry enough detail for operator review."""
        action = resolve_cursor_action(
            error=GatewayEmissionError(403, "governance_veto")
        )
        assert action.detail  # non-empty detail for logging
        assert "terminal" in action.detail.lower() or "403" in action.detail


# ---------------------------------------------------------------------------
# 429, 5xx, transport failure — retry/backoff (do NOT advance)
# ---------------------------------------------------------------------------


class TestRetryBackoff:
    """429, 5xx, transport failure: do NOT advance; retry with backoff."""

    def test_429_rate_limit(self) -> None:
        action = resolve_cursor_action(error=GatewayEmissionError(429, "rate_limited"))
        assert action.verdict == CursorVerdict.RETRY
        assert action.status == 429

    def test_500_server_error(self) -> None:
        action = resolve_cursor_action(
            error=GatewayEmissionError(500, "internal_server_error")
        )
        assert action.verdict == CursorVerdict.RETRY
        assert action.status == 500

    def test_502_bad_gateway(self) -> None:
        action = resolve_cursor_action(status=502, reason="bad_gateway")
        assert action.verdict == CursorVerdict.RETRY

    def test_503_unavailable(self) -> None:
        action = resolve_cursor_action(status=503)
        assert action.verdict == CursorVerdict.RETRY

    def test_transport_failure_status_zero(self) -> None:
        """Transport failure (status=0): transient; retry."""
        action = resolve_cursor_action(
            error=GatewayEmissionError(0, "transport_error:ConnectionRefusedError")
        )
        assert action.verdict == CursorVerdict.RETRY
        assert action.status == 0

    def test_poll_error_transport(self) -> None:
        """PollError from urllib transport fault."""
        action = resolve_cursor_action(
            error=PollError(0, "transport_error:TimeoutError")
        )
        assert action.verdict == CursorVerdict.RETRY
        assert action.status == 0

    def test_poll_error_5xx(self) -> None:
        """PollError with a 5xx status from provider."""
        action = resolve_cursor_action(
            error=PollError(500, "unexpected_status_expected_200")
        )
        assert action.verdict == CursorVerdict.RETRY


# ---------------------------------------------------------------------------
# Sensitive-data rejection — quarantine + alert (never silently advance)
# ---------------------------------------------------------------------------


class TestSensitiveRejection:
    """Sensitive-data rejection: do NOT silently advance; quarantine + alert."""

    def test_sensitive_data_explicit_reason(self) -> None:
        action = resolve_cursor_action(
            error=GatewayEmissionError(422, "sensitive_data_rejected")
        )
        assert action.verdict == CursorVerdict.QUARANTINE
        assert action.quarantine_reason == QuarantineReason.SENSITIVE_DATA_REJECTED
        assert action.status == 422

    def test_secret_detected(self) -> None:
        action = resolve_cursor_action(status=422, reason="secret_detected")
        assert action.verdict == CursorVerdict.QUARANTINE
        assert action.quarantine_reason == QuarantineReason.SENSITIVE_DATA_REJECTED

    def test_phi_detected(self) -> None:
        action = resolve_cursor_action(status=422, reason="phi_detected")
        assert action.verdict == CursorVerdict.QUARANTINE
        assert action.quarantine_reason == QuarantineReason.SENSITIVE_DATA_REJECTED

    def test_pan_detected(self) -> None:
        action = resolve_cursor_action(status=422, reason="pan_detected")
        assert action.verdict == CursorVerdict.QUARANTINE
        assert action.quarantine_reason == QuarantineReason.SENSITIVE_DATA_REJECTED

    def test_422_no_reason_defaults_sensitive(self) -> None:
        """A bare 422 with no reason defaults to sensitive rejection."""
        action = resolve_cursor_action(status=422, reason="")
        assert action.verdict == CursorVerdict.QUARANTINE
        assert action.quarantine_reason == QuarantineReason.SENSITIVE_DATA_REJECTED

    def test_quarantine_never_advances(self) -> None:
        """Quarantined items must NOT be silently advanced."""
        action = resolve_cursor_action(
            error=GatewayEmissionError(422, "sensitive_data_rejected")
        )
        assert action.verdict != CursorVerdict.ADVANCE

    def test_422_opaque_gateway_reason_quarantines(self) -> None:
        """The GatewaySink collapses a Bot 422 veto to the fixed token-safe
        ``gateway_rejected`` reason. That opaque 422 is the composed real path
        (GatewaySink -> resolve_cursor_action) and must fail closed to a
        sensitive-data quarantine, never advance."""
        action = resolve_cursor_action(
            error=GatewayEmissionError(422, "gateway_rejected")
        )
        assert action.verdict == CursorVerdict.QUARANTINE
        assert action.quarantine_reason == QuarantineReason.SENSITIVE_DATA_REJECTED
        assert action.status == 422


# ---------------------------------------------------------------------------
# Schema drift — quarantine (fail contract gate; do NOT advance)
# ---------------------------------------------------------------------------


class TestSchemaDrift:
    """Schema drift: do NOT advance; fail the contract gate."""

    def test_schema_invalid(self) -> None:
        action = resolve_cursor_action(status=400, reason="schema_invalid")
        assert action.verdict == CursorVerdict.QUARANTINE
        assert action.quarantine_reason == QuarantineReason.SCHEMA_DRIFT

    def test_schema_drift_reason(self) -> None:
        action = resolve_cursor_action(status=400, reason="schema_drift")
        assert action.verdict == CursorVerdict.QUARANTINE
        assert action.quarantine_reason == QuarantineReason.SCHEMA_DRIFT

    def test_envelope_malformed(self) -> None:
        action = resolve_cursor_action(
            error=GatewayEmissionError(400, "envelope_malformed")
        )
        assert action.verdict == CursorVerdict.QUARANTINE
        assert action.quarantine_reason == QuarantineReason.SCHEMA_DRIFT

    def test_schema_drift_does_not_advance(self) -> None:
        """Schema drift must not lose the cursor — fix-forward."""
        action = resolve_cursor_action(status=400, reason="schema_drift")
        assert action.verdict != CursorVerdict.ADVANCE

    def test_400_opaque_gateway_reason_quarantines(self) -> None:
        """A Bot 400 after the exact-match capability handshake can only be a
        stale envelope mapping. The GatewaySink's opaque ``gateway_rejected``
        reason must fail closed to a schema-drift quarantine, never advance."""
        action = resolve_cursor_action(
            error=GatewayEmissionError(400, "gateway_rejected")
        )
        assert action.verdict == CursorVerdict.QUARANTINE
        assert action.quarantine_reason == QuarantineReason.SCHEMA_DRIFT
        assert action.status == 400

    def test_protocol_mismatch_does_not_advance(self) -> None:
        action = resolve_cursor_action(
            error=GatewayEmissionError(
                0, "protocol_mismatch:contract_fingerprint_mismatch"
            )
        )
        assert action.verdict == CursorVerdict.QUARANTINE
        assert action.quarantine_reason == QuarantineReason.SCHEMA_DRIFT


# ---------------------------------------------------------------------------
# Crash between emit and cursor persist — at-least-once semantics
# ---------------------------------------------------------------------------


class TestAtLeastOnceSemantics:
    """Crash between emit and cursor persist: at-least-once, bot dedup expected.

    The policy itself does not implement dedup — it only ensures the cursor
    is NOT advanced on transient failures, enabling re-emission on restart.
    Bot-side dedup handles the idempotency guarantee.
    """

    def test_transport_failure_allows_reemit(self) -> None:
        """A transport failure (crash-like) → RETRY = cursor not advanced = re-emit."""
        action = resolve_cursor_action(
            error=GatewayEmissionError(0, "transport_error:ConnectionResetError")
        )
        assert action.verdict == CursorVerdict.RETRY

    def test_policy_does_not_own_dedup(self) -> None:
        """The policy module has no dedup state — confirm no dedup attributes."""
        import runtime.cursor_policy as mod

        # No dedup cache, no event-store state, no bot state
        assert not hasattr(mod, "DeliveryDedupCache")
        assert not hasattr(mod, "_event_store")


# ---------------------------------------------------------------------------
# Edge cases and input validation
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Input validation and boundary conditions."""

    def test_requires_error_or_status(self) -> None:
        with pytest.raises(ValueError, match="Either 'error' or 'status'"):
            resolve_cursor_action()

    def test_raw_status_and_reason(self) -> None:
        """Operator-runtime implementations can pass raw status+reason."""
        action = resolve_cursor_action(status=503, reason="service_unavailable")
        assert action.verdict == CursorVerdict.RETRY

    def test_unexpected_status_retries(self) -> None:
        """An unexpected status (e.g. 600) is conservatively retried."""
        action = resolve_cursor_action(status=600, reason="unknown")
        assert action.verdict == CursorVerdict.RETRY

    def test_action_is_frozen_dataclass(self) -> None:
        """CursorAction is immutable."""
        action = resolve_cursor_action(status=201)
        with pytest.raises(Exception):
            action.verdict = CursorVerdict.RETRY  # type: ignore[misc]
