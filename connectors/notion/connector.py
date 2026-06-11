# SPDX-License-Identifier: MIT
"""Notion connector: page events + page objects into neutral Observations.

Two surfaces with DIFFERENT input shapes (deep-audit 2026-06-12):

- **Webhook** (the live mode): the delivery body is a thin EVENT envelope --
  ``{id (event id), type, entity:{id,type}, timestamp, ...}`` -- that does NOT
  carry the changed page content (Notion docs: "the events do not contain the
  full content that changed"). ``parse_event`` maps it to a page-changed POINTER
  Observation keyed by the page ``entity.id`` (the stable subject), NOT the
  ephemeral event ``id``. The page title/url/body require the deferred
  ``pages.retrieve`` fetch.
- **Active fetch** (deferred): a full Notion page object flows through
  ``parse_page`` (title from the ``type == "title"`` property; block body is a
  further deferred fetch).

Notion signs deliveries ``X-Notion-Signature: sha256=<hex HMAC-SHA256(
verification_token, raw_body)>``; ``verify()`` REQUIRES the documented ``sha256=``
prefix (rejecting a bare-hex value), strips it, and reuses ``verify_hmac_hex``
(fail-closed, constant-time). Dedup is by event id with a body-hash fallback so a
signed id-less body cannot bypass it. The live API fetch, OAuth, and HTTP receipt
stay in the operator runtime (see ``auth.md``).
"""

from __future__ import annotations

import hashlib
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


def parse_event(envelope: dict) -> Observation:
    """Map a Notion webhook delivery envelope into a page-changed POINTER Observation.

    The envelope (``{id, type, entity:{id,type}, timestamp, ...}``) carries no page content, so
    the Observation is keyed by the page ``entity.id`` (the stable subject identity — NOT the
    ephemeral event ``id``), enabling dedup-by-subject and the deferred ``pages.retrieve`` fetch.
    ``entity.id`` is an opaque Notion UUID (pseudonymous, kept; SG-2026-06-05-D); the event type
    is an enum. No free-text → no redact needed. Title/url/body come from the deferred fetch.
    """
    entity = envelope.get("entity")
    entity = entity if isinstance(entity, dict) else {}
    page_id = str(entity.get("id") or "")
    event_type = str(envelope.get("type") or "")
    label = f"Notion {event_type}".strip() if event_type else "Notion page change"
    return Observation(
        source_ref=SourceRef(
            source_id="notion",
            ref=page_id or "notion-page",  # subject = page entity.id, never the event id
            kind="page",
        ),
        excerpt=f"{label} ({page_id})" if page_id else label,
        mode=SourceMode.WEBHOOK,
        title=label,
        author="",  # webhook envelope carries no author; the deferred fetch would supply it
        timestamp=str(envelope.get("timestamp") or ""),
    )


def parse_page(page: dict) -> Observation:
    """Map a full Notion page object (the deferred active-fetch shape) into an Observation."""
    page_id = str(page.get("id") or "")  # str-guard: a non-string id must not crash _is_blank
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
        """The webhook EVENT id (top-level ``id``) for replay dedup; '' when absent.

        Dedup keys on the event id (a replay re-sends the same event id), NOT the page
        ``entity.id`` — two distinct changes to one page are distinct events, not duplicates.
        """
        return str(payload.get("id") or "")

    def normalize_event(self, *, headers: dict[str, str], body: bytes) -> list[Observation]:
        """Self-guard (re-verify), dedup (body-hash fallback), then parse the envelope. ``[]`` on reject."""
        if not self.verify(headers=headers, body=body):
            return []
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):  # ValueError covers JSONDecodeError + huge-int (#55)
            return []
        if not isinstance(payload, dict):
            return []
        if self._dedup is not None:
            # body-hash fallback: a signed id-less body cannot bypass dedup (deep-audit; #60 pattern).
            delivery_id = self._delivery_id(payload) or hashlib.sha256(body).hexdigest()
            if self._dedup.is_duplicate("notion", delivery_id):
                return []
            self._dedup.mark_seen("notion", delivery_id)
        return [parse_event(payload)]  # webhook body is the EVENT envelope, not a full page object
