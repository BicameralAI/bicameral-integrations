# SPDX-License-Identifier: MIT
"""Fathom meeting connector: provider payloads into neutral Observations.

A Fathom meeting object — a REST `GET /meetings` list item or a
`new-meeting-content-ready` webhook payload (same shape) — maps to one
provider-neutral Observation. Provider field knowledge stays here; the
universal adapter (`pipeline.normalize`) turns it into an AdapterEmission
(ADR-0004). ``verify()`` is IMPLEMENTED: Svix-style webhook signature
verification via ``adapter.core.webhook_security.verify_standard_webhook``
(freshness window; malformed header types fail closed — #57). The live REST
poll transport + API-key/secret resolution stay in the operator runtime; see
``auth.md``.
"""

from __future__ import annotations

import dataclasses
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
    verify_standard_webhook,
)


def _s(value: object) -> str:
    """A string for str inputs, else '' (provider fields may drift non-str — parse-robustness)."""
    return value if isinstance(value, str) else ""


def _flatten_transcript(segments: list | None) -> str:
    """Join transcript segments into bare spoken-text lines.

    The Fathom ``segment.speaker.display_name`` is a REAL name; it is **dropped**, not surfaced —
    identity minimization covers a name a connector would INJECT into emitted text, not just the
    ``author`` slot (SG-2026-06-12-H; honors the "real names dropped" guarantee). Spoken ``text``
    is still PII-dense and is redact-and-passed by the caller. ``None``/empty yields ``""``.
    """
    lines: list[str] = []
    for seg in segments or []:
        if not isinstance(seg, dict):
            continue
        text = _s(seg.get("text"))
        if text:
            lines.append(text)
    return "\n".join(lines)


def parse_meeting(meeting: dict) -> Observation:
    """Map a Fathom meeting object into a provider-neutral Observation.

    Transcript + summary + title are PII-dense free text -> **redact-and-pass** (scrubs
    secret/PHI/PAN + email/phone; FX-SEC-001 is the un-bypassable backstop), matching the
    granola/devin standard. Speaker + recorder real names are dropped (not surfaced). The excerpt
    is the redacted transcript, falling back to the redacted summary then the redacted title so the
    non-empty-excerpt rule always holds.
    """
    recording_id = meeting.get("recording_id", "")
    title = redact(
        _s(meeting.get("meeting_title"))
        or _s(meeting.get("title"))
        or str(recording_id)
    )
    ds = meeting.get(
        "default_summary"
    )  # isinstance guard: a truthy non-dict must floor, not crash
    summary = _s(ds.get("markdown_formatted")) if isinstance(ds, dict) else ""
    excerpt = redact(_flatten_transcript(meeting.get("transcript")) or summary) or title
    return Observation(
        source_ref=SourceRef(
            source_id="fathom",
            ref=str(recording_id),
            url=_s(meeting.get("share_url")) or _s(meeting.get("url")),
            kind="meeting",
        ),
        excerpt=excerpt,
        mode=SourceMode.PASSIVE,
        title=title,
        author="",  # recorded_by.name (real-name PII) dropped (SG-2026-06-11-D); speaker names too (-H)
        timestamp=_s(meeting.get("recording_end_time"))
        or _s(meeting.get("created_at")),
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
        if not isinstance(
            payload, dict
        ):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_meeting(payload)]

    def verify(self, *, headers: dict[str, str], body: bytes) -> bool:
        """Verify the Svix signature + freshness; fail closed on any error."""
        try:
            verify_standard_webhook(
                headers=headers, body=body, secret=self._secret, now=self._clock()
            )
            return True
        except (
            WebhookVerificationError,
            AttributeError,
            TypeError,
        ):  # malformed header types fail closed (#57)
            return False

    def normalize_event(
        self, *, headers: dict[str, str], body: bytes
    ) -> list[Observation]:
        """Self-guard (re-verify), dedup on webhook-id, then parse. ``[]`` on reject."""
        if not self.verify(headers=headers, body=body):
            return []
        delivery_id = header_value(headers, "webhook-id") or ""
        if self._dedup is not None:
            if not delivery_id or self._dedup.is_duplicate("fathom", delivery_id):
                return []
            self._dedup.mark_seen("fathom", delivery_id)
        try:
            payload = json.loads(body)
        except (
            ValueError,
            UnicodeDecodeError,
        ):  # ValueError covers JSONDecodeError + huge-int (#55)
            return []
        obs_list = self.observations(payload)
        if delivery_id:
            obs_list = [
                dataclasses.replace(o, provider_event_id=delivery_id) for o in obs_list
            ]
        return obs_list
