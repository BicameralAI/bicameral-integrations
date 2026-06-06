# SPDX-License-Identifier: MIT
"""MCP Registry connector: server.json entries into neutral Observations.

An MCP Registry ``server.json`` entry (trust tier T1, read-only scoring /
allowlist) maps to one provider-neutral Observation. Read-only evidence
(ADR-0008); the live registry fetch is deferred (see ``auth.md``).
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation


def parse_server(entry: dict) -> Observation:
    """Map an MCP Registry server.json entry into a provider-neutral Observation."""
    name = entry.get("name") or ""
    title = entry.get("title") or name
    repo = entry.get("repository") or {}
    url = repo.get("url") or entry.get("websiteUrl") or ""
    return Observation(
        source_ref=SourceRef(
            source_id="mcp_registry",
            ref=name or title or "mcp-server",
            url=url,
            kind="mcp_server",
        ),
        excerpt=entry.get("description") or title or name or "mcp-server",
        mode=SourceMode.ACTIVE,
        title=title or name or "mcp-server",
        metadata={
            "version": entry.get("version") or "",
            "repository_source": repo.get("source") or "",
        },
    )


class McpRegistryConnector:
    """MCP Registry connector identity plus the server-entry parse surface.

    Trust tier T1, read-only scoring/allowlist. The live registry-fetch path is
    deferred; this is the parse surface.
    """

    source_id = "mcp_registry"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.ACTIVE}))

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_server(payload)]
