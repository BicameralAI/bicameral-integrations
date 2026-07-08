# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""Typed discovery outcome and contract types for provider acquisition.

These types model the result of discovery operations (list, get, validate,
fetch) against provider resources. They are **provider facts**, not Bicameral
evidence or governance objects.

Authority boundary: nothing here carries SourceBinding, SourceSnapshot,
SourceEvidence, DecisionCandidate, review commands, signoff, compliance,
event-store write intent, or local actor authority.

Provider writes (``create_provider_resource``) are explicitly excluded from the
discovery surface and belong to the egress / proposed-action territory.

Schema provenance: provisional alpha from BicameralAI/bicameral-bot#462.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


# ---------------------------------------------------------------------------
# Permission / action-needed outcomes
# ---------------------------------------------------------------------------


class PermissionState(StrEnum):
    """Permission state for the authenticated connection to a resource."""

    GRANTED = "granted"
    UNKNOWN = "unknown"
    ACTION_NEEDED = "action_needed"
    DENIED = "denied"


class DiscoveryErrorKind(StrEnum):
    """Typed reasons a discovery operation could not succeed."""

    PERMISSION_DENIED = "permission_denied"
    ACTION_NEEDED = "action_needed"
    NOT_FOUND = "not_found"
    UNSUPPORTED = "unsupported"
    PROVIDER_ERROR = "provider_error"


# ---------------------------------------------------------------------------
# Discovery outcome envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscoveryError:
    """Structured error for a failed discovery operation."""

    kind: DiscoveryErrorKind
    message: str
    permission_state: PermissionState | None = None
    action_hint: str | None = None


@dataclass(frozen=True)
class DiscoveryOutcome[T]:
    """Result envelope for any discovery operation.

    Exactly one of ``value`` or ``error`` is populated.
    """

    value: T | None = None
    error: DiscoveryError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.value is not None


# ---------------------------------------------------------------------------
# Provider resource descriptor (mirrors JSON schema)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FreshnessMetadata:
    """Provider-reported freshness metadata."""

    last_modified: str | None = None
    etag: str | None = None
    item_count: int | None = None


@dataclass(frozen=True)
class ResourceRef:
    """Lightweight reference to a parent or related resource."""

    resource_id: str
    display_name: str | None = None


@dataclass(frozen=True)
class ProviderResourceDescriptor:
    """Typed representation of a provider-hosted resource descriptor.

    Maps 1-to-1 with the ``provider-resource-descriptor.schema.json`` golden
    schema.  Carries provider facts only.
    """

    provider: str
    resource_id: str
    display_name: str
    resource_type: str
    captured_at: str
    uri: str | None = None
    capabilities: tuple[str, ...] = ()
    permission: PermissionState | None = None
    freshness: FreshnessMetadata | None = None
    parent: ResourceRef | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Provider item envelope (mirrors JSON schema)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderItemEnvelope:
    """Typed representation of a fetched provider item envelope.

    Maps 1-to-1 with the ``provider-item-envelope.schema.json`` golden
    schema.  Content is screened — must not contain secrets, tokens,
    credentials, or PII.
    """

    provider: str
    resource_id: str
    item_id: str
    item_type: str
    content: str
    fetched_at: str
    title: str | None = None
    uri: str | None = None
    content_hash: str | None = None
    freshness: FreshnessMetadata | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)
