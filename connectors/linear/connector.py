# SPDX-License-Identifier: MIT
"""Linear webhook and GraphQL connector into provider-neutral Observations.

Provider-specific parsing and source-aware heuristic features stay here. Every
Observation is normalized and universally evaluated by ``adapter.core.pipeline``.
"""

from __future__ import annotations

import dataclasses
import json
import time
from collections.abc import Callable
from typing import Any

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
_ADMINISTRATIVE_UPDATE_FIELDS = frozenset(
    {
        "assigneeId",
        "cycleId",
        "estimate",
        "labelIds",
        "priority",
        "projectId",
        "stateId",
        "teamId",
    }
)


def _signal(
    code: str,
    basis: str,
    confidence: str,
    effect: str,
    explanation: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "scope": "integration",
        "basis": basis,
        "confidence": confidence,
        "recommended_effect": effect,
        "explanation": explanation,
        "schema_version": 1,
    }


def _integration_signals(event: dict) -> list[dict[str, Any]]:
    """Derive Linear-aware, fail-open advisory signals."""
    signals: list[dict[str, Any]] = []
    actor = event.get("actor") if isinstance(event.get("actor"), dict) else {}
    actor_type = str(actor.get("type", "")).strip().lower()
    if actor_type and actor_type not in {"user", "member"}:
        signals.append(
            _signal(
                "generated_sync_event",
                "linear_non_user_actor_type",
                "medium",
                "rank_lower",
                "Linear reports a non-user actor for this event.",
            )
        )

    updated_from = event.get("updatedFrom")
    if event.get("action") == "update" and isinstance(updated_from, dict) and updated_from:
        changed_fields = {str(key) for key in updated_from}
        if changed_fields.issubset(_ADMINISTRATIVE_UPDATE_FIELDS):
            signals.append(
                _signal(
                    "administrative_only",
                    "linear_updated_from_administrative_fields",
                    "high",
                    "rank_lower",
                    "Linear reports only administrative issue-field changes.",
                )
            )
    return signals


def _is_issue_event(payload: dict) -> bool:
    """Admit only create/update Issue events with a stable identifier."""
    if payload.get("type") != "Issue":
        return False
    if payload.get("action") == "remove":
        return False
    data = payload.get("data")
    return isinstance(data, dict) and bool(data.get("identifier"))


def parse_event(event: dict) -> Observation:
    """Map a Linear webhook event into a provider-neutral Observation."""
    data = event.get("data") or {}
    identifier = data.get("identifier") or data.get("id") or ""
    resource_id = str(data.get("id") or identifier)
    name = data.get("title") or ""
    title = f"{identifier}: {name}".strip(": ").strip() or identifier
    excerpt = data.get("description") or name or identifier
    actor = event.get("actor") if isinstance(event.get("actor"), dict) else {}
    metadata = {
        "action": event.get("action", ""),
        "type": event.get("type", ""),
        "organization_id": event.get("organizationId", ""),
        "actor_type": actor.get("type", ""),
        "advisory_signals": _integration_signals(event),
    }
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
        author="",
        timestamp=event.get("createdAt") or "",
        provider_event_id=str(event.get("webhookId") or ""),
        provider_resource_id=f"issue:{resource_id}",
        evidence_id=f"linear:issue:{resource_id}:{event.get('createdAt') or ''}",
        evidence_metadata=metadata,
        metadata=metadata,
    )


def parse_issue_node(node: dict) -> Observation:
    """Map one Linear GraphQL Issue node into a neutral Observation."""
    identifier = node.get("identifier") or node.get("id") or ""
    resource_id = str(node.get("id") or identifier)
    name = node.get("title") or ""
    title = f"{identifier}: {name}".strip(": ").strip() or identifier
    excerpt = node.get("description") or name or identifier
    state = node.get("state") or {}
    metadata = {
        "state": state.get("name", "") if isinstance(state, dict) else "",
        "advisory_signals": [],
    }
    return Observation(
        source_ref=SourceRef(
            source_id="linear",
            ref=identifier,
            url=node.get("url") or "",
            kind="issue",
        ),
        excerpt=excerpt,
        mode=SourceMode.ACTIVE,
        title=title,
        timestamp=node.get("updatedAt") or "",
        provider_resource_id=f"issue:{resource_id}",
        evidence_id=f"linear:issue:{resource_id}:{node.get('updatedAt') or ''}",
        evidence_metadata=metadata,
        metadata=metadata,
    )


class LinearConnector:
    """Linear connector identity plus signed-webhook and GraphQL parse surfaces."""

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
        self._secret = secret
        self._dedup = dedup
        self._clock = clock or time.time

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):
            return []
        if not _is_issue_event(payload):
            return []
        return [parse_event(payload)]

    def _timestamp_ok(self, data: dict, now_ms: float) -> bool:
        ts = int(data["webhookTimestamp"])
        return abs(now_ms - ts) <= _REPLAY_WINDOW_MS

    def verify(self, *, headers: dict[str, str], body: bytes) -> bool:
        """Verify HMAC first, then enforce the Linear replay window."""
        try:
            verify_hmac_hex(
                header_sig=header_value(headers, "Linear-Signature"),
                body=body,
                secret=self._secret,
            )
            data = json.loads(body)
            return self._timestamp_ok(data, self._clock() * 1000)
        except (
            WebhookVerificationError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            KeyError,
            ValueError,
            TypeError,
        ):
            return False

    def normalize_event(
        self, *, headers: dict[str, str], body: bytes
    ) -> list[Observation]:
        """Self-guard, deduplicate by webhookId, and parse admitted events."""
        if not self.verify(headers=headers, body=body):
            return []
        payload = json.loads(body)
        if not _is_issue_event(payload):
            return []
        delivery_id = str(payload.get("webhookId") or "")
        if self._dedup is not None:
            if not delivery_id or self._dedup.is_duplicate("linear", delivery_id):
                return []
            self._dedup.mark_seen("linear", delivery_id)
        obs = parse_event(payload)
        return [dataclasses.replace(obs, provider_event_id=delivery_id)]
