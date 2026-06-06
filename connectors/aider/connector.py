# SPDX-License-Identifier: MIT
"""Aider connector: attributed git commits into neutral Observations.

Aider (aider.chat) auto-commits its edits and, by default, attributes them — it
appends ``(aider)`` to the git author/committer name, or (opt-in) adds a
``Co-authored-by:`` trailer. That git attribution is Aider's most stable,
documented, code-free provenance surface; each attributed commit record maps to
one provider-neutral Observation (trust tier T0, git import). The live git-log
walk, the ``--analytics-log`` JSONL, and the unversioned chat-history transcript
are deferred (see ``auth.md``); this is the parse surface only. Read-only
evidence, no canonical writes (ADR-0008).
"""

from __future__ import annotations

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation


def _trailer_texts(record: dict) -> list[str]:
    """Trailers as plain strings (entries may be strings or {key,value} dicts)."""
    out: list[str] = []
    for entry in record.get("trailers") or []:
        if isinstance(entry, dict):
            out.append(f"{entry.get('key', '')}: {entry.get('value', '')}")
        else:
            out.append(str(entry))
    return out


def _attributed_by(record: dict) -> str:
    """Which channel carries the Aider attribution, or '' if none is present.

    Name fields are coerced to ``str`` so a malformed record (non-string field)
    is classified, not crashed.
    """
    if "(aider)" in str(record.get("author_name") or ""):
        return "author"
    if "(aider)" in str(record.get("committer_name") or ""):
        return "committer"
    for text in _trailer_texts(record):
        if "Co-authored-by" in text and "aider" in text.lower():
            return "co-author"
    return ""


def parse_commit(record: dict) -> Observation:
    """Map an Aider-attributed git commit record into a provider-neutral Observation.

    Field values are coerced to ``str`` and stripped where the emission contract
    needs a non-blank string, so a malformed record (non-string or
    whitespace-only field) is normalized to a terminal literal, not crashed and
    not silently blank.
    """
    message = record.get("message")
    subject = message.split("\n", 1)[0].strip() if isinstance(message, str) else ""
    commit_hash = str(record.get("hash") or "").strip()
    excerpt = subject or commit_hash or "aider-commit"
    return Observation(
        source_ref=SourceRef(source_id="aider", ref=commit_hash or "aider-commit", kind="commit"),
        excerpt=excerpt,
        mode=SourceMode.PASSIVE,
        title=subject or commit_hash or "aider-commit",
        author=str(record.get("author_name") or ""),
        timestamp=str(record.get("authored_at") or ""),
        metadata={"attributed_by": _attributed_by(record), "short_hash": commit_hash[:7]},
    )


class AiderConnector:
    """Aider connector identity plus the git-commit parse surface.

    Trust tier T0 (git import). The live git-log walk + analytics/chat-history
    secondary modes are deferred; this is the parse surface.
    """

    source_id = "aider"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.PASSIVE}))

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_commit(payload)]
