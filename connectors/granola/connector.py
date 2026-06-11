"""Granola notes connector: provider payloads into neutral, redacted Observations.

Verified against public-api.granola.ai docs (2026-06-11): host ``public-api.granola.ai/v1``,
resource ``GET /notes?include=transcript``. A note carries ``id`` (``not_`` prefix), ``title``,
``summary``, ``owner`` {name, email}, and an embedded ``transcript`` array of
``{speaker:{source, diarization_label}, text}``.

PII contract (purple-team L2, SG-2026-06-11-D): meeting content is PII-dense and the provider
gives NO redaction guidance, so the transcript + title are passed through
``adapter.core.redaction.redact`` (redact-and-pass — scrubs secret/PHI/PAN + email/phone), and
the meeting **owner's identity is NEVER surfaced** as author (dropped, not redacted — FX-SEC-001
does not catch a generic name and redact() does not scrub a bare name). The live HTTP poll
(cursor ``cursor``/``hasMore``), the ``created_after`` watermark, and key resolution stay in the
operator runtime (see ``auth.md``).
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.redaction import redact


def _join_transcript(item: dict) -> str:
    """Join the embedded `transcript` array's per-utterance `text` (verified shape:
    `transcript: [{speaker:{source,diarization_label}, text}, …]`), tolerating non-list /
    non-dict entries. `speaker` is an anonymized object (source/diarization label), never read."""
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
    """Map a Granola note into a redacted, provider-neutral Observation.

    Transcript + title are redact-and-passed; the owner's identity is dropped (PII-safe). The
    excerpt falls back to the (redacted) title, then a literal, so the non-empty rule holds.
    """
    note_id = str(item.get("id") or "")
    title = redact(str(item.get("title") or ""))
    text = redact(_join_transcript(item))
    return Observation(
        source_ref=SourceRef(
            source_id="granola", ref=note_id or "granola-note", kind="transcript"
        ),
        excerpt=text or title or "granola-note",
        mode=SourceMode.PASSIVE,
        title=title or note_id or "granola-note",
        author="",  # PII-safe: the meeting owner's name/email is NEVER surfaced (drop, not redact)
        timestamp=str(item.get("created_at") or ""),
    )


class GranolaConnector:
    """Granola connector identity plus the redacted transcript parse surface.

    Declares the passive polling mode; the live HTTP poll and watermark two-phase
    commit are deferred to the operator runtime.
    """

    source_id = "granola"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.PASSIVE}))

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_transcript(payload)]
