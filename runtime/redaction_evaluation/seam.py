# SPDX-License-Identifier: MIT
"""Spike-only backend seam: the detector interface every candidate implements.

The seam deliberately mirrors the shape suggested by ADR-0020. A backend
receives one admitted field's text and returns findings; it never sees the
whole record, never owns replacement, receipts, cursors, or failure policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .policy import RedactionPolicy


class BackendError(Exception):
    """Typed backend failure; ``reason`` must be value-free."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class BackendUnavailable(BackendError):
    """Package, model, or engine cannot be provisioned or initialized."""


class BackendInvalidConfiguration(BackendError):
    """The pinned candidate configuration is not usable."""


@dataclass(frozen=True)
class BackendIdentity:
    """Pinned identity of one candidate configuration."""

    candidate_id: str
    family: str
    engine_version: str
    packages: dict[str, str] = field(default_factory=dict)
    models: dict[str, str] = field(default_factory=dict)
    configuration: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class BackendFinding:
    """One detected span inside one admitted field.

    ``category`` and ``subtype`` are already normalized to the candidate-neutral
    taxonomy by the backend's versioned label map. ``backend_label`` and
    ``confidence`` are diagnostic-only and never reach a production-style
    receipt.
    """

    category: str
    subtype: str
    start: int
    end: int
    backend_label: str = ""
    confidence: float | None = None


@dataclass(frozen=True)
class BackendHealth:
    """Value-free readiness report."""

    ready: bool
    detail: str = ""


class RedactionBackend(Protocol):
    """Detection-only candidate interface behind the Bicameral wrapper."""

    @property
    def identity(self) -> BackendIdentity: ...

    def initialize(self) -> None: ...

    def analyze(
        self,
        text: str,
        *,
        field_path: str,
        policy: RedactionPolicy,
    ) -> list[BackendFinding]: ...

    def health(self) -> BackendHealth: ...
