# SPDX-License-Identifier: MIT
"""Notion connector: page objects into neutral Observations.

A Notion page object (trust tier T1) maps to one provider-neutral Observation.
The page title is read from the property whose ``type == "title"``. Page body
(blocks) is a separate fetch and is deferred; the excerpt is the title. Notion
signs webhook deliveries ``X-Notion-Signature: sha256=<hex HMAC-SHA256(
verification_token, raw_body)>``; ``verify()`` REQUIRES the documented
``sha256=`` prefix (rejecting a bare-hex value), strips it, and reuses
``verify_hmac_hex`` (fail-closed, constant-time). The live API fetch, OAuth, and
HTTP receipt stay in the operator runtime (see ``auth.md``).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.redaction import redact
from adapter.core.webhook_security import (
    DeliveryDedupCache,
    WebhookVerificationError,
    header_value,
    verify_hmac_hex,
)


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
    # The page title is free-text -> redact-and-pass (FX-SEC-001 alone does not catch a generic
    # email/name in a title). Terminal non-empty floor: an untitled page without a usable id
    # (partial objects / webhook envelopes) falls through to a literal (SARIF/MCP-Registry pattern).
    # author is the OPAQUE created_by.id (a Notion user UUID) -- pseudonymous, kept (SG-2026-06-05-D).
    title = redact(_page_title(page.get("properties") or {})) or page_id or "notion-page"
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

    def __init__(
        self,
        *,
        secret: str = "",
        dedup: DeliveryDedupCache | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        # Secret (the subscription verification_token) injected; resolution
        # stays in the operator runtime.
        self._secret = secret
        self._dedup = dedup
        self._clock = clock or time.time

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_page(payload)]

    def verify(self, *, headers: dict[str, str], body: bytes) -> bool:
        """X-Notion-Signature ``sha256=`` hex HMAC over the raw body. Fail closed.

        The ``sha256=`` prefix is REQUIRED (Notion always sends it); a bare-hex
        value is rejected rather than accepted, pinning the provider's one form.
        """
        try:
            sig = header_value(headers, "X-Notion-Signature")
            if not isinstance(sig, str) or not sig.lower().startswith("sha256="):
                return False
            verify_hmac_hex(header_sig=sig[len("sha256="):], body=body, secret=self._secret)
            return True
        except (WebhookVerificationError, AttributeError, TypeError):
            return False

    def _delivery_id(self, payload: dict) -> str:
        """Best-effort delivery id ('' when none derivable; entity guarded)."""
        entity = payload.get("entity")
        entity_id = entity.get("id") if isinstance(entity, dict) else None
        return str(payload.get("id") or entity_id or "")

    def normalize_event(self, *, headers: dict[str, str], body: bytes) -> list[Observation]:
        """Self-guard (re-verify), dedup, then parse. ``[]`` on reject."""
        if not self.verify(headers=headers, body=body):
            return []
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):  # ValueError covers JSONDecodeError + huge-int (#55)
            return []
        if not isinstance(payload, dict):
            return []
        if self._dedup is not None:
            delivery_id = self._delivery_id(payload)
            if delivery_id and self._dedup.is_duplicate("notion", delivery_id):
                return []
            self._dedup.mark_seen("notion", delivery_id)
        return [parse_page(payload)]
