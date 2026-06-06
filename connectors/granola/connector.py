"""Granola transcript connector: provider payloads into neutral Observations.

A Granola meeting-transcript item maps to one provider-neutral Observation.
Port of the parse shape from `bicameral-mcp` `events/sources/granola.py`,
reduced to the neutral surface; the live HTTP poll, watermark two-phase commit,
and API-key resolution stay in the operator runtime (see ``auth.md``).
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation


def _first_participant_name(participants: list | None) -> str:
    """Return the first participant's display name, tolerating str or dict."""
    for first in participants or []:
        if isinstance(first, dict):
            return str(first.get("name") or "")
        if isinstance(first, str):
            return first
        return ""
    return ""


def parse_transcript(item: dict) -> Observation:
    """Map a Granola transcript item into a provider-neutral Observation.

    The excerpt is the transcript text, falling back to the title so the
    contract's non-empty-excerpt rule holds.
    """
    transcript_id = str(item.get("id") or "")
    text = str(item.get("transcript_text") or "")
    title = str(item.get("title") or "") or transcript_id
    return Observation(
        source_ref=SourceRef(source_id="granola", ref=transcript_id, kind="transcript"),
        excerpt=text or title,
        mode=SourceMode.PASSIVE,
        title=title,
        author=_first_participant_name(item.get("participants")),
        timestamp=str(item.get("ended_at") or ""),
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
