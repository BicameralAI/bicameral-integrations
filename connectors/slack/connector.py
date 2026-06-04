# SPDX-License-Identifier: MIT
"""Slack connector: message events into neutral Observations.

A Slack message — a bare message object or an Events-API ``event_callback``
envelope — maps to one provider-neutral Observation (read/ingest evidence
surface, trust tier T2). Notify/write (T3+) is deferred (ADR-0008,
evidence-before-action). Slack signs requests ``X-Slack-Signature: v0=<hex
HMAC-SHA256(signing_secret, "v0:{ts}:{raw_body}")>`` with an
``X-Slack-Request-Timestamp`` (5-minute replay window); ``verify()`` reuses
``verify_slack_signature`` (fail-closed, constant-time). The ``url_verification``
handshake and unverified deliveries normalize to ``[]``. The live Events-API
receipt + secret resolution stay in the operator runtime (see ``auth.md``).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.webhook_security import (
    DeliveryDedupCache,
    WebhookVerificationError,
    header_value,
    verify_slack_signature,
)


def parse_message(payload: dict) -> Observation:
    """Map a Slack message (or event_callback envelope) into an Observation.

    Slack messages routinely have empty ``text`` (system messages, join/leave);
    the excerpt falls back to a stripped-non-empty locating string so the
    emission contract's non-empty-excerpt rule always holds. Edit subtypes
    (``message_changed`` et al.) carry their real content in a nested
    ``message`` object, which is unwrapped so the edited text is not lost.
    """
    event = payload.get("event")
    msg = event if isinstance(event, dict) else payload
    nested = msg.get("message")
    inner = nested if isinstance(nested, dict) else {}
    channel = msg.get("channel") or inner.get("channel") or ""
    ts = msg.get("ts") or inner.get("ts") or ""
    excerpt = (msg.get("text") or inner.get("text") or "").strip() or f"(no text) {channel}:{ts}"
    return Observation(
        source_ref=SourceRef(source_id="slack", ref=f"{channel}:{ts}", kind="message"),
        excerpt=excerpt,
        mode=SourceMode.WEBHOOK,
        author=msg.get("user") or inner.get("user") or "",
        timestamp=ts,
        metadata={"channel": channel, "type": msg.get("type") or ""},
    )


class SlackConnector:
    """Slack connector identity plus the message parse surface.

    Trust tier T2 (read/ingest). The live Events-API receipt + signature
    verification path and any notify/write (T3+) are deferred.
    """

    source_id = "slack"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.WEBHOOK}))

    def __init__(
        self,
        *,
        secret: str = "",
        dedup: DeliveryDedupCache | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        # Secret injected (keyring resolution stays in the operator runtime).
        self._secret = secret
        self._dedup = dedup
        self._clock = clock or time.time

    def observations(self, payload: dict) -> list[Observation]:
        return [parse_message(payload)]

    def verify(self, *, headers: dict[str, str], body: bytes) -> bool:
        """Slack ``v0`` signature over ``v0:{ts}:{body}`` + replay window. Fail closed."""
        try:
            verify_slack_signature(
                signature=header_value(headers, "X-Slack-Signature"),
                timestamp=header_value(headers, "X-Slack-Request-Timestamp"),
                body=body,
                secret=self._secret,
                now=self._clock(),
            )
            return True
        except (WebhookVerificationError, AttributeError, TypeError):
            return False

    def _delivery_id(self, payload: dict) -> str:
        """Best-effort delivery id (Events-API ``event_id``; '' when none)."""
        return str(payload.get("event_id") or "")

    def normalize_event(self, *, headers: dict[str, str], body: bytes) -> list[Observation]:
        """Self-guard (re-verify), drop the handshake, dedup, parse. ``[]`` on reject."""
        if not self.verify(headers=headers, body=body):
            return []
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return []
        if not isinstance(payload, dict):
            return []
        if payload.get("type") == "url_verification":  # signed handshake, no event
            return []
        if self._dedup is not None:
            delivery_id = self._delivery_id(payload)
            if delivery_id and self._dedup.is_duplicate("slack", delivery_id):
                return []
            self._dedup.mark_seen("slack", delivery_id)
        return [parse_message(payload)]
