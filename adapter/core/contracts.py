"""Connector and universal adapter interface contracts."""

from __future__ import annotations

from typing import Protocol

from .capabilities import SourceCapabilities
from .emissions import SourceRef
from .observations import Observation


class Connector(Protocol):
    """Base identity contract shared by every provider connector."""

    source_id: str
    capabilities: SourceCapabilities


class ActiveConnector(Connector, Protocol):
    """Operator-initiated URL or source-ref fetch."""

    def can_handle_ref(self, ref: SourceRef) -> bool:
        """Return True when this connector can fetch the source ref."""
        ...

    def fetch_active(self, ref: SourceRef) -> list[Observation]:
        """Fetch a source ref into provider-neutral observations."""
        ...


class PollingConnector(Connector, Protocol):
    """Configured passive pull with two-phase cursor confirmation."""

    def pull(self, *, config: dict, cursor: dict | None = None) -> list[Observation]:
        """Pull source items newer than the provided cursor as observations."""
        ...

    def confirm(self) -> dict | None:
        """Confirm the pending cursor after downstream ingest succeeds."""
        ...


class WebhookConnector(Connector, Protocol):
    """Provider webhook verification and event normalization."""

    def verify(self, *, headers: dict[str, str], body: bytes) -> bool:
        """Verify provider authenticity before parsed fields are trusted."""
        ...

    def normalize_event(
        self, *, headers: dict[str, str], body: bytes
    ) -> list[Observation]:
        """Parse a verified webhook event into provider-neutral observations."""
        ...
