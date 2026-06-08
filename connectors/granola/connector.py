"""Granola notes connector: provider payloads into neutral Observations.

Verified against docs.granola.ai (2026-06-08): the public API host is
``public-api.granola.ai/v1`` and the resource is ``GET /notes`` with
``?include=transcript`` (there is no ``/transcripts`` collection). A note (with its
embedded transcript) maps to one provider-neutral Observation. The live HTTP poll
(cursor pagination ``cursor``/``hasMore``), the ``created_after`` watermark two-phase
commit, and API-key resolution stay in the operator runtime (see ``auth.md``).
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation


def _first_attendee_name(attendees: list | None) -> str:
    """First attendee's display name, tolerating str or dict (verified field: `attendees`)."""
    for first in attendees or []:
        if isinstance(first, dict):
            return str(first.get("name") or "")
        if isinstance(first, str):
            return first
        return ""
    return ""


def _join_transcript(item: dict) -> str:
    """Join the embedded `transcript` array's per-utterance `text` (verified shape:
    `transcript: [{speaker, text}, …]`), tolerating non-list / non-dict entries."""
    transcript = item.get("transcript")
    if not isinstance(transcript, list):
        return ""
    parts = [
        str(utt["text"]).strip()
        for utt in transcript
        if isinstance(utt, dict) and isinstance(utt.get("text"), str) and utt["text"].strip()
    ]
    return " ".join(parts)


def parse_transcript(item: dict) -> Observation:
    """Map a Granola note (with embedded transcript) into a provider-neutral Observation.

    The excerpt is the joined transcript text, falling back to the title so the
    contract's non-empty-excerpt rule holds.
    """
    note_id = str(item.get("id") or "")
    text = _join_transcript(item)
    title = str(item.get("title") or "") or note_id
    return Observation(
        source_ref=SourceRef(source_id="granola", ref=note_id, kind="transcript"),
        excerpt=text or title,
        mode=SourceMode.PASSIVE,
        title=title,
        author=_first_attendee_name(item.get("attendees")),
        timestamp=str(item.get("created_at") or ""),
    )


class GranolaConnector:
    """Granola connector identity plus the transcript parse surface.

    Declares the passive polling mode; the live HTTP poll and watermark
    two-phase commit are deferred to the operator runtime.
    """

    source_id = "granola"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.PASSIVE}))

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_transcript(payload)]
