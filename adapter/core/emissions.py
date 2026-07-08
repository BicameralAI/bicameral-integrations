# SPDX-License-Identifier: MIT
"""Neutral emission objects produced by the universal adapter and consumed by mods."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class SourceRef:
    """Stable provider reference for a source artifact."""

    source_id: str
    ref: str
    url: str = ""
    kind: str = ""


@dataclass(frozen=True)
class SourceEvidence:
    """Reviewable evidence preserved from a source artifact."""

    source_ref: SourceRef
    excerpt: str
    author: str = ""
    timestamp: str = ""
    evidence_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConfidenceSurface:
    """Named confidence dimensions; never a single opaque score."""

    dimensions: dict[str, Literal["low", "medium", "high", "unknown"]]
    rationale: str = ""


@dataclass(frozen=True)
class RoutingHint:
    """Advisory review-routing metadata."""

    role: str
    reason: str
    priority: Literal["low", "normal", "high"] = "normal"


@dataclass(frozen=True)
class AdvisoryResult:
    """Non-authoritative mod or adapter advisory."""

    kind: str
    message: str
    evidence_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderProvenance:
    """Non-authoritative provider provenance facts attached to an emission.

    These fields are evidence metadata only — they carry no Bicameral
    governance authority, no bot-side ActorContext, and no accepted
    SourceBinding.  Bot owns canonical identity; integrations surface
    the raw provider-side delivery posture for dedup evidence and
    diagnostic tracing.
    """

    delivery_mode: Literal["webhook", "poll", "active-fetch"]
    verification: Literal["signed", "unsigned"]
    provider_event_id: str = ""
    provider_resource_id: str = ""


@dataclass(frozen=True)
class AdapterEmission:
    """Neutral object emitted by a source adapter."""

    source_id: str
    title: str
    body: str
    evidence: tuple[SourceEvidence, ...]
    emission_type: Literal["candidate", "evidence", "hint", "advisory"] = "candidate"
    adapter_version: str = "0.1.0"
    confidence: ConfidenceSurface | None = None
    routing_hints: tuple[RoutingHint, ...] = ()
    advisories: tuple[AdvisoryResult, ...] = ()
    provenance: ProviderProvenance | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
