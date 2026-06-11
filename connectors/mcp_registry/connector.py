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
from adapter.core.redaction import redact


def _str(value: object) -> str:
    """Coerce a scalar registry field to a string (``''`` when absent/non-string). A non-string
    name/title/description must not flow into a string field and crash ``_is_blank`` /
    ``detect_sensitive`` downstream, aborting the poll batch (deep-audit PARSE)."""
    return value if isinstance(value, str) else ""


def parse_server(entry: dict) -> Observation:
    """Map an MCP Registry server.json entry into a provider-neutral Observation.

    The registry is PUBLIC and fully attacker-publishable, so the free-text leaves
    (title/description/url) are third-party-controlled and **redact-and-passed** (FX-SEC-001
    screens secret/PHI/PAN but not a generic email/phone in free text). ``ref`` keeps the server
    name as the locator (the wire ``source`` ref/url is redacted again in gateway_mapping)."""
    name = _str(entry.get("name"))
    raw_title = _str(entry.get("title"))
    title = redact(raw_title or name)
    description = redact(_str(entry.get("description")))
    repo = entry.get("repository")
    repo = repo if isinstance(repo, dict) else {}  # untrusted boundary: a non-dict must not crash
    url = redact(_str(repo.get("url")) or _str(entry.get("websiteUrl")))
    return Observation(
        source_ref=SourceRef(
            source_id="mcp_registry",
            ref=name or raw_title or "mcp-server",
            url=url,
            kind="mcp_server",
        ),
        excerpt=description or title or "mcp-server",
        mode=SourceMode.ACTIVE,
        title=title or "mcp-server",
        metadata={
            "version": _str(entry.get("version")),
            "repository_source": _str(repo.get("source")),
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
