# Copyright 2026 Bicameral AI — MIT License
"""Fixture-backed discovery emitter stubs.

These stubs satisfy the ``DiscoveryConnector`` contract using the golden
fixtures from ``protocol/provider_acquisition/fixtures/``.  They require no
live provider credentials and are intended for contract-shape validation and
downstream integration testing.

Authority boundary: stubs emit **provider facts** only.  They never carry
SourceBinding, SourceSnapshot, SourceEvidence, DecisionCandidate, review
commands, signoff, compliance, event-store write intent, or local actor
authority.  ``create_provider_resource`` is explicitly absent — provider writes
belong to the egress / proposed-action territory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .types import (
    DiscoveryError,
    DiscoveryErrorKind,
    DiscoveryOutcome,
    FreshnessMetadata,
    PermissionState,
    ProviderItemEnvelope,
    ProviderResourceDescriptor,
)

_ROOT = Path(__file__).resolve().parent
_DESCRIPTOR_DIR = _ROOT / "fixtures" / "descriptors"
_ITEMS_DIR = _ROOT / "fixtures" / "items"


# ---------------------------------------------------------------------------
# Fixture loading helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_meta(data: dict[str, Any]) -> dict[str, Any]:
    """Remove underscore-prefixed metadata keys (comments, boundary notes)."""
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _parse_freshness(raw: dict[str, Any] | None) -> FreshnessMetadata | None:
    if raw is None:
        return None
    return FreshnessMetadata(
        last_modified=raw.get("last_modified"),
        etag=raw.get("etag"),
        item_count=raw.get("item_count"),
    )


def _parse_descriptor(data: dict[str, Any]) -> ProviderResourceDescriptor:
    clean = _strip_meta(data)
    perm_raw = clean.get("permission")
    permission = PermissionState(perm_raw) if perm_raw is not None else None
    return ProviderResourceDescriptor(
        provider=clean["provider"],
        resource_id=clean["resource_id"],
        display_name=clean["display_name"],
        resource_type=clean["resource_type"],
        captured_at=clean["captured_at"],
        uri=clean.get("uri"),
        capabilities=tuple(clean.get("capabilities", ())),
        permission=permission,
        freshness=_parse_freshness(clean.get("freshness")),
        provider_metadata=clean.get("provider_metadata", {}),
    )


def _parse_item(data: dict[str, Any]) -> ProviderItemEnvelope:
    clean = _strip_meta(data)
    return ProviderItemEnvelope(
        provider=clean["provider"],
        resource_id=clean["resource_id"],
        item_id=clean["item_id"],
        item_type=clean["item_type"],
        content=clean["content"],
        fetched_at=clean["fetched_at"],
        title=clean.get("title"),
        uri=clean.get("uri"),
        content_hash=clean.get("content_hash"),
        freshness=_parse_freshness(clean.get("freshness")),
        provider_metadata=clean.get("provider_metadata", {}),
    )


def _load_all_descriptors() -> list[ProviderResourceDescriptor]:
    """Load and parse all golden descriptor fixtures."""
    descriptors: list[ProviderResourceDescriptor] = []
    for path in sorted(_DESCRIPTOR_DIR.glob("*.json")):
        descriptors.append(_parse_descriptor(_load_json(path)))
    return descriptors


def _load_all_items() -> list[ProviderItemEnvelope]:
    """Load and parse all golden item fixtures."""
    items: list[ProviderItemEnvelope] = []
    for path in sorted(_ITEMS_DIR.glob("*.json")):
        items.append(_parse_item(_load_json(path)))
    return items


# ---------------------------------------------------------------------------
# Fixture-backed stub
# ---------------------------------------------------------------------------


class FixtureDiscoveryStub:
    """Fixture-backed discovery emitter stub.

    Satisfies the ``DiscoveryConnector`` protocol using golden fixtures.
    Does not require live provider credentials.

    ``create_provider_resource`` is intentionally absent — provider writes
    are egress / proposed-action territory, not discovery.
    """

    def __init__(self, source_id: str = "fixture-discovery-stub") -> None:
        self.source_id = source_id
        from adapter.core.capabilities import SourceCapabilities, SourceMode

        self.capabilities = SourceCapabilities(
            modes=frozenset({SourceMode.DISCOVERY}),
        )
        self._descriptors = _load_all_descriptors()
        self._items = _load_all_items()

    # -- list_resources -----------------------------------------------------

    def list_resources(
        self, *, config: dict[str, Any]
    ) -> DiscoveryOutcome[list[ProviderResourceDescriptor]]:
        provider_filter = config.get("provider")
        if provider_filter:
            filtered = [d for d in self._descriptors if d.provider == provider_filter]
        else:
            filtered = list(self._descriptors)
        return DiscoveryOutcome(value=filtered)

    # -- get_resource -------------------------------------------------------

    def get_resource(
        self, *, config: dict[str, Any], resource_id: str
    ) -> DiscoveryOutcome[ProviderResourceDescriptor]:
        for desc in self._descriptors:
            if desc.resource_id == resource_id:
                if desc.permission == PermissionState.DENIED:
                    return DiscoveryOutcome(
                        error=DiscoveryError(
                            kind=DiscoveryErrorKind.PERMISSION_DENIED,
                            message=f"Access denied for resource {resource_id}",
                            permission_state=PermissionState.DENIED,
                            action_hint=desc.provider_metadata.get("action_hint"),
                        )
                    )
                if desc.permission == PermissionState.ACTION_NEEDED:
                    return DiscoveryOutcome(
                        error=DiscoveryError(
                            kind=DiscoveryErrorKind.ACTION_NEEDED,
                            message=f"Action needed for resource {resource_id}",
                            permission_state=PermissionState.ACTION_NEEDED,
                            action_hint=desc.provider_metadata.get("action_hint"),
                        )
                    )
                return DiscoveryOutcome(value=desc)
        return DiscoveryOutcome(
            error=DiscoveryError(
                kind=DiscoveryErrorKind.NOT_FOUND,
                message=f"Resource {resource_id} not found in fixtures",
            )
        )

    # -- validate_resource_access -------------------------------------------

    def validate_resource_access(
        self, *, config: dict[str, Any], resource_id: str
    ) -> DiscoveryOutcome[ProviderResourceDescriptor]:
        for desc in self._descriptors:
            if desc.resource_id == resource_id:
                if desc.permission == PermissionState.DENIED:
                    return DiscoveryOutcome(
                        error=DiscoveryError(
                            kind=DiscoveryErrorKind.PERMISSION_DENIED,
                            message=f"Permission denied for {resource_id}",
                            permission_state=PermissionState.DENIED,
                            action_hint=desc.provider_metadata.get("action_hint"),
                        )
                    )
                if desc.permission == PermissionState.ACTION_NEEDED:
                    return DiscoveryOutcome(
                        error=DiscoveryError(
                            kind=DiscoveryErrorKind.ACTION_NEEDED,
                            message=f"Action needed for {resource_id}",
                            permission_state=PermissionState.ACTION_NEEDED,
                            action_hint=desc.provider_metadata.get("action_hint"),
                        )
                    )
                return DiscoveryOutcome(value=desc)
        return DiscoveryOutcome(
            error=DiscoveryError(
                kind=DiscoveryErrorKind.NOT_FOUND,
                message=f"Resource {resource_id} not found in fixtures",
            )
        )

    # -- fetch_provider_item ------------------------------------------------

    def fetch_provider_item(
        self, *, config: dict[str, Any], resource_id: str, item_id: str
    ) -> DiscoveryOutcome[ProviderItemEnvelope]:
        for item in self._items:
            if item.resource_id == resource_id and item.item_id == item_id:
                return DiscoveryOutcome(value=item)
        return DiscoveryOutcome(
            error=DiscoveryError(
                kind=DiscoveryErrorKind.NOT_FOUND,
                message=f"Item {item_id} not found in resource {resource_id}",
            )
        )
