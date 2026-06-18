"""Connector and universal adapter interface contracts.

Discovery is a fourth connector surface (peer to active/passive/webhook) that
is opt-in per connector.  It returns **provider facts** — not Bicameral
evidence or governance objects.  Provider writes (``create_provider_resource``)
are explicitly excluded from the discovery surface and belong to the
egress / proposed-action territory.  See integrations#173 and proposed
ADR-0017.
"""

from __future__ import annotations

from typing import Protocol

from .capabilities import SourceCapabilities
from .emissions import SourceRef
from .observations import Observation

# Re-export discovery types so callers can import from contracts if convenient.
from protocol.provider_acquisition.types import (  # noqa: F401
    DiscoveryOutcome,
    ProviderItemEnvelope,
    ProviderResourceDescriptor,
)


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


class DiscoveryConnector(Connector, Protocol):
    """Provider-fact discovery surface: list, get, validate, fetch.

    Discovery connectors emit ``ProviderResourceDescriptor`` and
    ``ProviderItemEnvelope`` objects — provider facts that carry no
    Bicameral governance, review, signoff, compliance, or event-store
    authority.

    ``create_provider_resource`` is **not** part of this interface.
    Provider writes belong to the egress / proposed-action territory.
    """

    def list_resources(
        self, *, config: dict
    ) -> DiscoveryOutcome[list[ProviderResourceDescriptor]]:
        """List discoverable resources from the provider."""
        ...

    def get_resource(
        self, *, config: dict, resource_id: str
    ) -> DiscoveryOutcome[ProviderResourceDescriptor]:
        """Get a single resource descriptor by provider-scoped id."""
        ...

    def validate_resource_access(
        self, *, config: dict, resource_id: str
    ) -> DiscoveryOutcome[ProviderResourceDescriptor]:
        """Validate that the authenticated connection can access a resource."""
        ...

    def fetch_provider_item(
        self, *, config: dict, resource_id: str, item_id: str
    ) -> DiscoveryOutcome[ProviderItemEnvelope]:
        """Fetch a single screened provider item from a resource.

        The returned envelope contains screened content — it must not be an
        unscreened side channel.
        """
        ...
