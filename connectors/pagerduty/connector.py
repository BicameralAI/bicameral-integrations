# SPDX-License-Identifier: MIT
"""PagerDuty connector: v3 incident webhook events into neutral Observations.

A PagerDuty v3 webhook envelope (`{event: {event_type, occurred_at, data}}`)
for an incident maps to one provider-neutral Observation (trust tier T1,
incident/on-call evidence). The live webhook receipt and `X-PagerDuty-Signature`
verification (which carries multiple comma-separated rotating signatures — the
deferred ``verify()`` must do membership, not equality) are deferred (see
``auth.md``); this is the parse surface only. Read-only evidence (ADR-0008).
"""

from __future__ import annotations

import hashlib
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
    verify_hmac_hex_multi,
)


def _text(value: object) -> str:
    """A stripped string for str inputs, else '' (webhook bodies carry any type)."""
    return value.strip() if isinstance(value, str) else ""


def parse_event(envelope: dict) -> Observation:
    """Map a PagerDuty v3 incident webhook envelope into an Observation.

    Unwraps the nested ``event.data`` envelope; both levels are isinstance-
    guarded so a malformed/partial payload normalizes rather than crashes.
    """
    event = envelope.get("event")
    ev = event if isinstance(event, dict) else envelope
    nested = ev.get("data")
    data = nested if isinstance(nested, dict) else {}
    iid = str(data.get("id") or "pagerduty-incident")
    title = _text(data.get("title")) or _text(data.get("summary"))
    return Observation(
        source_ref=SourceRef(
            source_id="pagerduty", ref=iid, url=data.get("html_url") or "", kind="incident"
        ),
        excerpt=title or iid,
        mode=SourceMode.WEBHOOK,
        title=title or iid,
        timestamp=str(data.get("created_at") or ev.get("occurred_at") or ""),
        metadata={
            "event_type": ev.get("event_type") or "",
            "status": data.get("status") or "",
            "urgency": data.get("urgency") or "",
        },
    )


class PagerDutyConnector:
    """PagerDuty connector identity, parse surface, and webhook verification.

    Trust tier T1. ``verify`` checks the ``X-PagerDuty-Signature`` multi-signature
    set (``v1=<hex>,v1=<hex>`` for zero-downtime rotation — accept if ANY matches)
    fail-closed. PagerDuty documents no replay-timestamp window, so dedup
    (best-effort, on the envelope ``event.id`` when present) is the only replay
    guard. The live HTTP receipt + secret resolution stay in the operator runtime.
    """

    source_id = "pagerduty"
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
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_event(payload)]

    def verify(self, *, headers: dict[str, str], body: bytes) -> bool:
        """Multi-signature ``v1=`` HMAC-SHA256 membership over the raw body. Fail closed."""
        try:
            verify_hmac_hex_multi(
                header_sig=header_value(headers, "X-PagerDuty-Signature"),
                body=body,
                secret=self._secret,
            )
            return True
        except (WebhookVerificationError, AttributeError, TypeError):
            return False

    def _delivery_id(self, payload: dict) -> str:
        """Best-effort delivery id (envelope ``event.id``; '' when none)."""
        event = payload.get("event")
        return str(event.get("id") or "") if isinstance(event, dict) else ""

    def normalize_event(self, *, headers: dict[str, str], body: bytes) -> list[Observation]:
        """Self-guard (re-verify), best-effort dedup, then parse. ``[]`` on reject."""
        if not self.verify(headers=headers, body=body):
            return []
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):  # ValueError covers JSONDecodeError + huge-int (#55)
            return []
        if not isinstance(payload, dict):  # valid JSON but not an object
            return []
        if self._dedup is not None:
            delivery_id = self._delivery_id(payload) or hashlib.sha256(body).hexdigest()  # body-hash fallback dedups id-less replays (#60)
            if self._dedup.is_duplicate("pagerduty", delivery_id):
                return []
            self._dedup.mark_seen("pagerduty", delivery_id)
        return [parse_event(payload)]
