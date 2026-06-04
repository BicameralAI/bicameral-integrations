# SPDX-License-Identifier: MIT
"""Notion connector: page objects into neutral Observations.

A Notion page object (trust tier T1) maps to one provider-neutral Observation.
The page title is read from the property whose ``type == "title"``. Page body
(blocks) is a separate fetch and is deferred; the excerpt is the title. Live
API fetch, OAuth, and webhooks are deferred (see ``auth.md``).
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation


def _page_title(properties: dict) -> str:
    """Join the plain_text of the property whose type is 'title'."""
    for prop in (properties or {}).values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            parts = [rt.get("plain_text") or "" for rt in (prop.get("title") or [])]
            return "".join(parts).strip()
    return ""


def parse_page(page: dict) -> Observation:
    """Map a Notion page object into a provider-neutral Observation."""
    page_id = page.get("id") or ""
    # Terminal non-empty floor: a page can arrive untitled AND without a usable
    # id (partial objects, webhook envelopes); the emission contract forbids a
    # blank excerpt, so fall through to a literal as SARIF/MCP-Registry do.
    title = _page_title(page.get("properties") or {}) or page_id or "notion-page"
    return Observation(
        source_ref=SourceRef(
            source_id="notion",
            ref=page_id,
            url=page.get("url") or "",
            kind="page",
        ),
        excerpt=title,
        mode=SourceMode.ACTIVE,
        title=title,
        author=(page.get("created_by") or {}).get("id") or "",
        timestamp=page.get("last_edited_time") or page.get("created_time") or "",
    )


class NotionConnector:
    """Notion connector identity plus the page parse surface.

    Trust tier T1. Declares active fetch + webhook modes; the live Notion API
    fetch, block-content retrieval, OAuth, and webhook verification are deferred.
    """

    source_id = "notion"
    capabilities = SourceCapabilities(
        modes=frozenset({SourceMode.ACTIVE, SourceMode.WEBHOOK})
    )

    def observations(self, payload: dict) -> list[Observation]:
        return [parse_page(payload)]
