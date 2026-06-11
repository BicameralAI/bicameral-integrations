"""Linear webhook connector: event payloads into neutral Observations.

A Linear webhook event envelope (``{action, type, actor, data, ...}``) for an
Issue maps to one provider-neutral Observation. The ``action`` / ``type`` /
``organizationId`` change-context fields are preserved in
``Observation.metadata`` for downstream diffing. Provider field knowledge stays
here; normalization is the universal adapter's job (ADR-0004). ``Linear-Signature``
verification (+ 60 s anti-replay) is built (``verify``/``normalize_event``); the live
GraphQL active-fetch parse surface (``parse_issue_node``) is built this cycle and driven
by ``runtime.graphql_poll`` — the live HTTP boundary + API-key resolution stay
operator-run (see ``auth.md``).
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
    verify_hmac_hex,
)

_REPLAY_WINDOW_MS = 60_000


def parse_event(event: dict) -> Observation:
    """Map a Linear webhook event into a provider-neutral Observation.

    The title combines the human identifier (e.g. ``PROJ-123``) with the issue
    title; the excerpt is the description, falling back to the title then the
    identifier so the contract's non-empty-excerpt rule holds.
    """
    data = event.get("data") or {}
    identifier = data.get("identifier") or data.get("id") or ""
    name = data.get("title") or ""
    title = f"{identifier}: {name}".strip(": ").strip() or identifier
    excerpt = data.get("description") or name or identifier
    return Observation(
        source_ref=SourceRef(
            source_id="linear",
            ref=identifier,
            url=data.get("url") or event.get("url") or "",
            kind=(event.get("type") or "issue").lower(),
        ),
        excerpt=excerpt,
        mode=SourceMode.WEBHOOK,
        title=title,
        author="",  # was actor.name (real-name PII reaching the mod chokepoint) — dropped per
        # SG-2026-06-11-D (jira/granola precedent); FX-SEC-001 does not screen a generic name.
        timestamp=event.get("createdAt") or "",
        metadata={
            "action": event.get("action", ""),
            "type": event.get("type", ""),
            "organization_id": event.get("organizationId", ""),
        },
    )


def parse_issue_node(node: dict) -> Observation:
    """Map one Linear GraphQL ``Issue`` node (active fetch) into a neutral Observation.

    The GraphQL node is the issue object directly (top-level ``identifier``/``title``/
    ``description``/``url``/``updatedAt``/``state``) — distinct from the webhook envelope
    ``parse_event`` reads. PII-safe: assignee/creator identity is NOT surfaced (FX-SEC-001
    is the backstop). Excerpt falls back title→identifier so the non-empty rule holds.
    """
    identifier = node.get("identifier") or node.get("id") or ""
    name = node.get("title") or ""
    title = f"{identifier}: {name}".strip(": ").strip() or identifier
    excerpt = node.get("description") or name or identifier
    state = node.get("state") or {}
    return Observation(
        source_ref=SourceRef(
            source_id="linear", ref=identifier, url=node.get("url") or "", kind="issue"
        ),
        excerpt=excerpt,
        mode=SourceMode.ACTIVE,
        title=title,
        timestamp=node.get("updatedAt") or "",
        metadata={"state": state.get("name", "") if isinstance(state, dict) else ""},
    )


class LinearConnector:
    """Linear connector identity plus the webhook-event parse surface.

    Declares the modes Linear supports: webhook delivery (primary — the
    envelope carries change context a poll cannot) and active GraphQL fetch
    (`parse_issue_node`, driven by `runtime.graphql_poll`). `Linear-Signature`
    verification is built; the live HTTP boundary stays operator-run.
    """

    source_id = "linear"
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
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_event(payload)]

    def _timestamp_ok(self, data: dict, now_ms: float) -> bool:
        ts = int(data["webhookTimestamp"])
        return abs(now_ms - ts) <= _REPLAY_WINDOW_MS

    def verify(self, *, headers: dict[str, str], body: bytes) -> bool:
        """HMAC first; only then parse the body for the timestamp window. Fail closed."""
        try:
            verify_hmac_hex(
                header_sig=header_value(headers, "Linear-Signature"),
                body=body,
                secret=self._secret,
            )
            data = json.loads(body)
            return self._timestamp_ok(data, self._clock() * 1000)
        except (WebhookVerificationError, json.JSONDecodeError, UnicodeDecodeError, KeyError, ValueError, TypeError):
            return False

    def normalize_event(
        self, *, headers: dict[str, str], body: bytes
    ) -> list[Observation]:
        """Self-guard (re-verify), dedup on webhookId, then parse. ``[]`` on reject."""
        if not self.verify(headers=headers, body=body):
            return []
        payload = json.loads(body)
        if self._dedup is not None:
            delivery_id = str(payload.get("webhookId") or "")
            if not delivery_id or self._dedup.is_duplicate("linear", delivery_id):
                return []
            self._dedup.mark_seen("linear", delivery_id)
        return [parse_event(payload)]
