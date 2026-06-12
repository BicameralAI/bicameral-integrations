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
from adapter.core.redaction import redact

# `[^<>]` (excludes `<` too) makes this linear: an unclosed `<` run can't be consumed by
# the inner class, so each anchor fails in O(1) instead of re-scanning to EOF — O(n) total (#50).
_TAG_RE = re.compile(r"<[^<>]*>")
_WS_RE = re.compile(r"\s+")


def _strip_storage_html(value: str) -> str:
    """Flatten a Confluence XHTML storage body to plain text.

    Best-effort **lossy** flattener, NOT a sanitizer: it removes tags, unescapes
    entities, and collapses whitespace. Script/style text content survives as
    plain text; the emission-time secret/PII screen (``pipeline._screen_sensitive``)
    is the security gate, not this function.
    """
    text = _TAG_RE.sub(" ", value or "")
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

    A Confluence page title + body are PII-dense free text (internal docs, names, emails) ->
    **redact-and-pass** (secret/PHI/PAN + email/phone scrubbed; the jira/github standard, since
    FX-SEC-001 backstops only secret/PHI/PAN). The excerpt is the redacted flattened storage text,
    falling back to the redacted title then a ``confluence-page`` terminal floor (so the
    non-blank-excerpt contract holds). The ``id`` ref + page URL are not redacted.
    """
    title = redact((content.get("title") or "").strip())
    storage = ((content.get("body") or {}).get("storage") or {}).get("value") or ""
    return Observation(
        source_ref=SourceRef(
            source_id="confluence",
            ref=str(content.get("id") or "confluence-page"),
            # the _links.webui slug carries the page TITLE -> redact the url too, else title PII
            # survives in source_ref.url even though the title field is redacted (purple-team
            # CONF-PII-URL-01). Residual: a URL-encoded email in the slug (e.g. %40) is not regex-
            # matchable -- the redacted title field is the canonical surface.
            url=redact(_page_url(content)),
            kind="page",
        ),
        excerpt=redact(_strip_storage_html(storage)) or title or "confluence-page",
        mode=SourceMode.ACTIVE,
        title=title or "confluence-page",
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
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_content(payload)]
