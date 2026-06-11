"""Fathom meeting connector: provider payloads into neutral Observations.

A Fathom meeting object — a REST `GET /meetings` list item or a
`new-meeting-content-ready` webhook payload (same shape) — maps to one
provider-neutral Observation. Provider field knowledge stays here; the
universal adapter (`pipeline.normalize`) turns it into an AdapterEmission
(ADR-0004). The live REST poll, API-key resolution, and Svix webhook
signature verification are deferred (no live API this cycle); see ``auth.md``.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.webhook_security import (
    DeliveryDedupCache,
    WebhookVerificationError,
    header_value,
    verify_standard_webhook,
)


def _flatten_transcript(segments: list | None) -> str:
    """Join transcript segments into ``"<speaker>: <text>"`` lines.

    The speaker name is nested at ``segment.speaker.display_name`` (Fathom
    shape); a segment with no speaker contributes its bare text. ``None`` or an
    empty list yields ``""`` so the caller can fall back to summary/title.
    """
    lines: list[str] = []
    for seg in segments or []:
        speaker = seg.get("speaker")
        name = speaker.get("display_name", "") if isinstance(speaker, dict) else (speaker or "")
        text = seg.get("text") or ""
        if not text:
            continue
        lines.append(f"{name}: {text}" if name else text)
    return "\n".join(lines)


def parse_meeting(meeting: dict) -> Observation:
    """Map a Fathom meeting object into a provider-neutral Observation.

    The excerpt is the flattened transcript, falling back to the default
    summary's markdown and then the title so the contract's non-empty-excerpt
    rule always holds.
    """
    recording_id = meeting.get("recording_id", "")
    title = meeting.get("meeting_title") or meeting.get("title") or str(recording_id)
    summary = (meeting.get("default_summary") or {}).get("markdown_formatted") or ""
    excerpt = _flatten_transcript(meeting.get("transcript")) or summary or title
    return Observation(
        source_ref=SourceRef(
            source_id="fathom",
            ref=str(recording_id),
            url=meeting.get("share_url") or meeting.get("url") or "",
            kind="meeting",
        ),
        excerpt=excerpt,
        mode=SourceMode.PASSIVE,
        title=title,
        author="",  # was recorded_by.name (real-name PII reaching the mod chokepoint) — dropped
        # per SG-2026-06-11-D (jira/granola precedent); FX-SEC-001 does not screen a generic name.
        timestamp=meeting.get("recording_end_time") or meeting.get("created_at") or "",
    )


class FathomConnector:
    """Fathom connector identity plus the meeting-payload parse surface.

    Declares the modes Fathom supports: passive REST polling and the
    `new-meeting-content-ready` webhook. The live poll/credential path and
    Svix signature verification are deferred; this is the parse surface both
    modes share.
    """

    source_id = "fathom"
    capabilities = SourceCapabilities(
        modes=frozenset({SourceMode.PASSIVE, SourceMode.WEBHOOK})
    )

    def __init__(
        self,
        *,
        secret: str = "",
        dedup: DeliveryDedupCache | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        # Secret is injected (keyring resolution stays in the operator runtime).
        self._secret = secret
        self._dedup = dedup
        self._clock = clock or time.time

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_meeting(payload)]

    def verify(self, *, headers: dict[str, str], body: bytes) -> bool:
        """Verify the Svix signature + freshness; fail closed on any error."""
        try:
            verify_standard_webhook(
                headers=headers, body=body, secret=self._secret, now=self._clock()
            )
            return True
        except (WebhookVerificationError, AttributeError, TypeError):  # malformed header types fail closed (#57)
            return False

    def normalize_event(
        self, *, headers: dict[str, str], body: bytes
    ) -> list[Observation]:
        """Self-guard (re-verify), dedup on webhook-id, then parse. ``[]`` on reject."""
        if not self.verify(headers=headers, body=body):
            return []
        if self._dedup is not None:
            delivery_id = header_value(headers, "webhook-id") or ""
            if not delivery_id or self._dedup.is_duplicate("fathom", delivery_id):
                return []
            self._dedup.mark_seen("fathom", delivery_id)
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):  # ValueError covers JSONDecodeError + huge-int (#55)
            return []
        return [parse_meeting(payload)]
