# SPDX-License-Identifier: MIT
"""Zendesk connector: support-ticket webhook events into neutral Observations.

A Zendesk event-subscription webhook (`{type, account_id, subject, time,
detail, event}`) for a ticket maps to one provider-neutral Observation (trust
tier T1, support/customer evidence). The excerpt is the ticket **subject** (a
plain string) — never a description/comment body, which is customer-PII-dense
(SG-2026-06-04-M discipline: summary, not body). Deliveries are signed
``X-Zendesk-Webhook-Signature: base64(HMAC-SHA256(secret, timestamp + body))``
with ``X-Zendesk-Webhook-Signature-Timestamp``; ``verify()`` reuses
``verify_zendesk_signature``, fail-closed + constant-time. Zendesk documents no
replay window, so best-effort dedup is the only replay guard. The live REST poll
/ Events ingest, OAuth, secret resolution, and a **redaction-and-pass model for
live ticket-body ingest** are deferred (see ``auth.md``); this is the parse +
verify surface on synthetic fixtures. Read-only evidence, no canonical writes
(ADR-0008); the producer sensitive screen (``FX-SEC-001``) is the PII guard.
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
    verify_zendesk_signature,
)


def _text(value: object) -> str:
    """A stripped string for str inputs, else '' (wire payloads carry any type)."""
    return value.strip() if isinstance(value, str) else ""


def _nested(obj: dict, key: str, attr: str) -> str:
    """`obj[key][attr]` as text when both levels are dicts, else '' (SG-I)."""
    value = obj.get(key)
    return _text(value.get(attr)) if isinstance(value, dict) else ""


def _ticket_id(detail: dict, event: dict) -> str:
    """Ticket id from ``detail.id``, else parse ``subject`` (`zen:ticket:<id>`), else floor."""
    direct = _text(detail.get("id"))
    if direct:
        return direct
    subject = _text(event.get("subject"))
    if subject.startswith("zen:ticket:"):
        return subject[len("zen:ticket:"):] or "zendesk-ticket"
    return "zendesk-ticket"


def parse_ticket(event: dict) -> Observation:
    """Map a Zendesk ticket webhook event into a provider-neutral Observation."""
    detail = event.get("detail")
    detail = detail if isinstance(detail, dict) else {}
    tid = _ticket_id(detail, event)
    subject = _text(detail.get("subject"))  # ticket subject (str); never the body
    return Observation(
        source_ref=SourceRef(
            source_id="zendesk",
            ref=tid,
            url=_text(detail.get("url")),
            kind="ticket",
        ),
        excerpt=subject or tid,
        mode=SourceMode.WEBHOOK,
        title=subject or tid,
        author=_text(detail.get("requester_id")),
        timestamp=_text(detail.get("updated_at")) or _text(event.get("time")),
        metadata={
            "event_type": _text(event.get("type")) or _nested(event, "event", "type"),
            "status": _text(detail.get("status")),
            "priority": _text(detail.get("priority")),
            "via": _nested(detail, "via", "channel"),
        },
    )


class ZendeskConnector:
    """Zendesk connector identity, parse surface, and webhook verification.

    Trust tier T1. ``verify`` checks ``X-Zendesk-Webhook-Signature`` (Base64
    HMAC-SHA256 over ``timestamp + body``) fail-closed; Zendesk documents no
    replay window, so best-effort dedup is the only replay guard. The live REST
    receipt + secret resolution stay in the operator runtime.
    """

    source_id = "zendesk"
    capabilities = SourceCapabilities(
        modes=frozenset({SourceMode.WEBHOOK, SourceMode.ACTIVE})
    )

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
        return [parse_ticket(payload)]

    def verify(self, *, headers: dict[str, str], body: bytes) -> bool:
        """Base64 HMAC-SHA256 over ``timestamp + body``. Fail closed."""
        try:
            verify_zendesk_signature(
                signature=header_value(headers, "X-Zendesk-Webhook-Signature"),
                timestamp=header_value(headers, "X-Zendesk-Webhook-Signature-Timestamp"),
                body=body,
                secret=self._secret,
            )
            return True
        except (WebhookVerificationError, AttributeError, TypeError):
            return False

    def _delivery_id(self, payload: dict) -> str:
        """Best-effort delivery id ('' when none) — envelope ``id`` then ``detail.id``."""
        return _text(payload.get("id")) or _nested(payload, "detail", "id")

    def normalize_event(self, *, headers: dict[str, str], body: bytes) -> list[Observation]:
        """Self-guard (re-verify), best-effort dedup, then parse. ``[]`` on reject."""
        if not self.verify(headers=headers, body=body):
            return []
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return []
        if not isinstance(payload, dict):
            return []
        if self._dedup is not None:
            delivery_id = self._delivery_id(payload)
            if delivery_id and self._dedup.is_duplicate("zendesk", delivery_id):
                return []
            self._dedup.mark_seen("zendesk", delivery_id)
        return [parse_ticket(payload)]
