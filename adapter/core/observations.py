# SPDX-License-Identifier: MIT
"""Provider-neutral observations produced by connectors before normalization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .capabilities import SourceMode
from .emissions import SourceRef


@dataclass(frozen=True)
class Observation:
    """Provider-neutral raw capture a connector produces before normalization.

    Connectors own provider-specific parsing and yield Observations; the
    universal adapter (``pipeline.normalize``) is the single normalizer that turns
    any Observation into a reviewable ``AdapterEmission`` (ADR-0004 seam).

    ``advisory_signals`` may be supplied inside ``metadata`` using the shared
    fail-open heuristic schema. Evidence identity and evidence metadata are
    explicit fields so the universal normalizer can preserve recorded provenance
    without provider-specific emission construction.
    """

    source_ref: SourceRef
    excerpt: str
    mode: SourceMode = SourceMode.ACTIVE
    title: str = ""
    author: str = ""
    timestamp: str = ""
    provider_event_id: str = ""
    provider_resource_id: str = ""
    evidence_id: str = ""
    evidence_metadata: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
