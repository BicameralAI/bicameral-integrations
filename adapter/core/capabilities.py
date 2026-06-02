"""Connector capability declarations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SourceMode(StrEnum):
    """Supported integration entry modes."""

    ACTIVE = "active"
    PASSIVE = "passive"
    WEBHOOK = "webhook"
    DISCOVERY = "discovery"


@dataclass(frozen=True)
class SourceCapabilities:
    """Declared behavior for a source connector."""

    modes: frozenset[SourceMode]
    supports_filters: bool = False
    supports_quotas: bool = False
    supports_resource_overrides: bool = False
    source_specific_filters: frozenset[str] = field(default_factory=frozenset)

    def supports(self, mode: SourceMode) -> bool:
        return mode in self.modes
