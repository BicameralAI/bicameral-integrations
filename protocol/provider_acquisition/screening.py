# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""Fail-closed screening for discovery descriptors / items (ADR-0017 §3).

Reuses the adapter's single sensitive-data catalog
(``adapter.core.sensitive.detect_sensitive``) — one catalog, two entry points (the
emission screen in ``pipeline._screen_sensitive`` and this descriptor / item
screen). This is **not** a fork of detection.

Provider metadata is attacker-influenced (a folder named after a secret, a
PAN-shaped display name, an issue body carrying a leaked token), so every string
leaf of a descriptor / item is scanned **before the object crosses the boundary**.
A hit fails closed: the object is rejected and the matched value never travels in
the error. Shared so the GitHub (#180) and Google Drive (#179) connectors screen
identically.
"""

from __future__ import annotations

from typing import Any

from adapter.core.sensitive import detect_sensitive

from .types import ProviderItemEnvelope, ProviderResourceDescriptor


class DiscoveryScreenError(ValueError):
    """A descriptor / item carried sensitive data and was rejected.

    The message names the offending field path + the sensitive class only — never
    the matched value (which the catalog has already body-redacted, but we do not
    surface it at all here).
    """


def _string_leaves(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    """Flatten every string leaf of a nested value to ``(json_path, text)`` pairs."""
    out: list[tuple[str, str]] = []
    if isinstance(value, str):
        out.append((prefix or "<root>", value))
    elif isinstance(value, dict):
        for key, val in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            out.extend(_string_leaves(val, child))
    elif isinstance(value, (list, tuple)):
        for idx, val in enumerate(value):
            out.extend(_string_leaves(val, f"{prefix}[{idx}]"))
    return out


def _screen_leaves(leaves: list[tuple[str, str]]) -> None:
    for path, text in leaves:
        hits = detect_sensitive(text)
        if hits:
            raise DiscoveryScreenError(f"{path}: sensitive {hits[0].cls} detected")


def screen_descriptor(descriptor: ProviderResourceDescriptor) -> ProviderResourceDescriptor:
    """Return ``descriptor`` unchanged, or raise :class:`DiscoveryScreenError`.

    Scans display name, resource type, uri, capabilities, permission, parent,
    freshness, and every provider-metadata key/value. ``resource_id`` / ``provider``
    are identifiers but are scanned too (cheap; a secret-shaped id is still a leak).
    """
    leaves = _string_leaves(
        {
            "provider": descriptor.provider,
            "resource_id": descriptor.resource_id,
            "display_name": descriptor.display_name,
            "resource_type": descriptor.resource_type,
            "uri": descriptor.uri,
            "capabilities": list(descriptor.capabilities),
            "permission": descriptor.permission.value if descriptor.permission else None,
            "parent": (
                {
                    "resource_id": descriptor.parent.resource_id,
                    "display_name": descriptor.parent.display_name,
                }
                if descriptor.parent
                else None
            ),
            "freshness": (
                {
                    "last_modified": descriptor.freshness.last_modified,
                    "etag": descriptor.freshness.etag,
                }
                if descriptor.freshness
                else None
            ),
            "provider_metadata": descriptor.provider_metadata,
        }
    )
    _screen_leaves(leaves)
    return descriptor


def screen_item(item: ProviderItemEnvelope) -> ProviderItemEnvelope:
    """Return ``item`` unchanged, or raise :class:`DiscoveryScreenError`.

    The item ``content`` (an issue / PR body, a file excerpt) is the primary leak
    surface — it is scanned alongside title, uri, and provider metadata.
    """
    leaves = _string_leaves(
        {
            "provider": item.provider,
            "resource_id": item.resource_id,
            "item_id": item.item_id,
            "item_type": item.item_type,
            "title": item.title,
            "content": item.content,
            "uri": item.uri,
            "provider_metadata": item.provider_metadata,
        }
    )
    _screen_leaves(leaves)
    return item
