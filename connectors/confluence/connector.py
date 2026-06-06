"""Confluence connector: page content objects into neutral Observations.

The Confluence Cloud REST content shape is ``{id, type, title, body: {storage:
{value, representation}}, _links: {base, webui}}``. ``parse_content`` flattens the
XHTML ``storage`` body to review text. Verification is **deferred**: Confluence
Cloud has no doc-confirmed payload signature (the HMAC ``X-Hub-Signature`` scheme
is Confluence Data-Center only), so this connector ships the parse surface and is
proven through the poll path. The live REST fetch + Connect-JWT auth stay in the
operator runtime (see ``auth.md``).
"""

from __future__ import annotations

import html
import re
from urllib.parse import urlsplit

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation

_WS_RE = re.compile(r"\s+")


def _strip_storage_html(value: str) -> str:
    """Flatten a Confluence XHTML storage body to plain text.

    Best-effort **lossy** flattener, NOT a sanitizer: it removes tags, unescapes
    entities, and collapses whitespace. Script/style text content survives as
    plain text; the emission-time secret/PII screen (``pipeline._screen_sensitive``)
    is the security gate, not this function.
    """
    raw = value or ""
    parts: list[str] = []
    pos = 0
    while True:
        start = raw.find("<", pos)
        if start == -1:
            parts.append(raw[pos:])
            break
        parts.append(raw[pos:start])
        end = raw.find(">", start + 1)
        if end == -1:
            parts.append(raw[start:])
            break
        parts.append(" ")
        pos = end + 1
    text = "".join(parts)
    return _WS_RE.sub(" ", html.unescape(text)).strip()


def _page_url(content: dict) -> str:
    """Join ``_links.base`` + ``_links.webui`` into the page URL (best-effort)."""
    links = content.get("_links") or {}
    base = (links.get("base") or "").rstrip("/")
    webui = links.get("webui") or ""
    if base and webui:
        return base + webui
    return webui or base


def parse_content(content: dict) -> Observation:
    """Map a Confluence Cloud REST content object into a provider-neutral Observation.

    The excerpt is the flattened storage text, falling back to the title and then
    a ``confluence-page`` terminal floor (so the non-blank-excerpt contract holds).
    """
    title = (content.get("title") or "").strip()
    storage = ((content.get("body") or {}).get("storage") or {}).get("value") or ""
    return Observation(
        source_ref=SourceRef(
            source_id="confluence",
            ref=str(content.get("id") or title or "confluence-page"),
            url=_page_url(content),
            kind="page",
        ),
        excerpt=_strip_storage_html(storage) or title or "confluence-page",
        mode=SourceMode.ACTIVE,
        title=title,
    )


class ConfluenceConnector:
    """Confluence connector identity plus the page-content parse surface.

    Declares the modes Confluence supports (active REST fetch, passive polling,
    webhook). Only the parse surface ships this cycle; verification is deferred
    (the Cloud signature scheme is unverifiable from current docs — see
    ``auth.md``), so the connector is proven through the poll path.
    """

    source_id = "confluence"
    capabilities = SourceCapabilities(
        modes=frozenset({SourceMode.ACTIVE, SourceMode.PASSIVE, SourceMode.WEBHOOK})
    )

    def can_handle_ref(self, ref: SourceRef) -> bool:
        if ref.source_id == "confluence":
            return True
        # Match on the URL host, not a substring (py/incomplete-url-substring-sanitization).
        host = (urlsplit(ref.url).hostname or "").lower()
        return host.endswith(".atlassian.net")

    def observations(self, payload: dict) -> list[Observation]:
        return [parse_content(payload)]
