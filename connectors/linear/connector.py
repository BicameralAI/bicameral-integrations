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


def _integration_signals(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive Linear-aware, fail-open advisory signals."""
    signals: list[dict[str, Any]] = []
    actor_raw = event.get("actor")
    actor: dict[str, Any] = actor_raw if isinstance(actor_raw, dict) else {}
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


def _is_issue_event(payload: dict[str, Any]) -> bool:
    """Admit only create/update Issue events with a stable identifier."""
    if payload.get("type") != "Issue":
        return False
    if payload.get("action") == "remove":
        return False
    data = payload.get("data")
    return isinstance(data, dict) and bool(data.get("identifier"))


def parse_event(event: dict[str, Any]) -> Observation:
    """Map a Linear webhook event into a provider-neutral Observation."""
    data_raw = event.get("data")
    data: dict[str, Any] = data_raw if isinstance(data_raw, dict) else {}
    identifier = str(data.get("identifier") or data.get("id") or "")
    resource_id = str(data.get("id") or identifier)
    name = str(data.get("title") or "")
    title = f"{identifier}: {name}".strip(": ").strip() or identifier
    excerpt = str(data.get("description") or name or identifier)
    actor_raw = event.get("actor")
    actor: dict[str, Any] = actor_raw if isinstance(actor_raw, dict) else {}
    metadata: dict[str, Any] = {
        "action": str(event.get("action") or ""),
        "type": str(event.get("type") or ""),
        "organization_id": str(event.get("organizationId") or ""),
        "actor_type": str(actor.get("type") or ""),
        "advisory_signals": _integration_signals(event),
    }
    return Observation(
        source_ref=SourceRef(
            source_id="linear",
            ref=identifier,
            url=str(data.get("url") or event.get("url") or ""),
            kind=str(event.get("type") or "issue").lower(),
        ),
        excerpt=excerpt,
        mode=SourceMode.WEBHOOK,
        title=title,
        author="",
        timestamp=str(event.get("createdAt") or ""),
        provider_event_id=str(event.get("webhookId") or ""),
        provider_resource_id=f"issue:{resource_id}",
        evidence_id=f"linear:issue:{resource_id}:{event.get('createdAt') or ''}",
        evidence_metadata=metadata,
        metadata=metadata,
    )


def parse_issue_node(node: dict[str, Any]) -> Observation:
    """Map one Linear GraphQL Issue node into a neutral Observation."""
    identifier = str(node.get("identifier") or node.get("id") or "")
    resource_id = str(node.get("id") or identifier)
    name = str(node.get("title") or "")
    title = f"{identifier}: {name}".strip(": ").strip() or identifier
    excerpt = str(node.get("description") or name or identifier)
    state_raw = node.get("state")
    state: dict[str, Any] = state_raw if isinstance(state_raw, dict) else {}
    metadata: dict[str, Any] = {
        "state": str(state.get("name") or ""),
        "advisory_signals": [],
    }
    return Observation(
        source_ref=SourceRef(
            source_id="linear",
            ref=identifier,
            url=str(node.get("url") or ""),
            kind="issue",
        ),
        excerpt=excerpt,
        mode=SourceMode.ACTIVE,
        title=title,
        timestamp=str(node.get("updatedAt") or ""),
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

    def observations(self, payload: dict[str, Any]) -> list[Observation]:
        if not isinstance(payload, dict):
            return []
        if not _is_issue_event(payload):
            return []
        return [parse_event(payload)]

    def _timestamp_ok(self, data: dict[str, Any], now_ms: float) -> bool:
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
            decoded = json.loads(body)
            if not isinstance(decoded, dict):
                return False
            return self._timestamp_ok(decoded, self._clock() * 1000)
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
        decoded = json.loads(body)
        if not isinstance(decoded, dict):
            return []
        payload: dict[str, Any] = decoded
        if not _is_issue_event(payload):
            return []
        delivery_id = str(payload.get("webhookId") or "")
        if self._dedup is not None:
            if not delivery_id or self._dedup.is_duplicate("linear", delivery_id):
                return []
            self._dedup.mark_seen("linear", delivery_id)
        obs = parse_event(payload)
        return [dataclasses.replace(obs, provider_event_id=delivery_id)]
