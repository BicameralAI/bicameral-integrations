# SPDX-License-Identifier: MIT
"""MCP Registry connector: server entries into neutral Observations.

An MCP Registry server entry (trust tier T1, read-only scoring / allowlist) maps to one
provider-neutral Observation. Verified contract (registry.modelcontextprotocol.io
/openapi.yaml, 2026-06-08): the **public, no-auth** ``GET /v0/servers`` list wraps entries
under ``servers``; each entry nests the server under ``server`` (``{server, _meta}``), so the
runtime poll spec unwraps ``element.server`` before ``parse_server`` reads
``name``/``title``/``description``/``repository``/``websiteUrl``/``version``. Cursor pagination:
request ``cursor``, response token ``metadata.nextCursor`` (no has-more — stop on absent).
Read-only evidence (ADR-0008); the live HTTP poll stays in the operator runtime (see ``auth.md``).
Stage: **Beta**.
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation


def parse_server(entry: dict) -> Observation:
    """Map an MCP Registry server.json entry into a provider-neutral Observation."""
    name = entry.get("name") or ""
    title = entry.get("title") or name
    repo = entry.get("repository")
    repo = repo if isinstance(repo, dict) else {}  # untrusted boundary: a non-dict must not crash
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

    Trust tier T1, read-only scoring/allowlist. The live public list poll runs in the
    operator runtime via ``build_mcp_registry_spec`` (no auth, cursor-paginated); this
    class is the parse surface it feeds. Stage: Beta.
    """

    source_id = "mcp_registry"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.ACTIVE}))

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_server(payload)]
