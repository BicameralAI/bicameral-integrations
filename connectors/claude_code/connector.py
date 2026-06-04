# SPDX-License-Identifier: MIT
"""Claude Code connector: session-transcript JSONL lines into Observations.

Claude Code writes session transcripts as local JSONL at
``~/.claude/projects/<project-slug>/<session-id>.jsonl`` — a heterogeneous,
append-only event log (trust tier T0, file import). Only ``user`` / ``assistant``
/ ``summary`` lines carry evidence; every other ``type`` (``mode``,
``attachment``, ``file-history-snapshot``, ``last-prompt``, and unknown future
kinds) is skipped (``parse_session_line`` returns ``None``). The format is
documented but **unversioned at the line level**, so every field access is
defended and unknown record kinds are skipped, not errored (SG-2026-06-04-I).
One assistant turn may span several lines (one per content block); each line
maps to at most one Observation. The live file-watch + ``history.jsonl`` +
git-attribution paths are deferred (see ``auth.md``). Read-only evidence, no
canonical writes (ADR-0008); transcripts carry secrets/PII, so the producer
sensitive screen (``FX-SEC-001``) is the guard — this connector never redacts.
"""

from __future__ import annotations

from collections.abc import Iterable

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation

_EVIDENCE_TYPES = frozenset({"user", "assistant", "summary"})


def _text(value: object, _depth: int = 0) -> str:
    """A stripped string for str inputs, else '' (lines carry any type).

    ``tool_result`` content is sometimes a block list; recursion is depth-capped
    so a hostile/corrupt transcript with deeply-nested lists cannot raise
    ``RecursionError`` (SG-2026-06-04-I — skip, never crash).
    """
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list) and _depth < 4:
        return " ".join(
            _text(v.get("text") if isinstance(v, dict) else v, _depth + 1) for v in value
        ).strip()
    return ""


def _block_text(block: dict) -> str:
    """Evidence text for one assistant/user content block ('' to skip)."""
    btype = block.get("type")
    if btype == "text":
        return _text(block.get("text"))
    if btype == "tool_use":
        return f"[tool_use:{_text(block.get('name')) or 'tool'}]"
    if btype == "tool_result":
        return _text(block.get("content"))
    return ""  # thinking / unknown → skip


def _line_excerpt(line: dict, kind: str, ref: str) -> str:
    """First human-meaningful text, else a terminal non-empty literal (SG-G)."""
    msg = line.get("message")
    msg = msg if isinstance(msg, dict) else {}
    content = msg.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = [_block_text(b) for b in content if isinstance(b, dict)]
        joined = " ".join(p for p in parts if p).strip()
        if joined:
            return joined
    if kind == "summary":
        summary = _text(line.get("summary"))
        if summary:
            return summary
    return f"[claude-code:{kind}] {ref}"


def parse_session_line(line: dict) -> Observation | None:
    """Map one transcript line to an Observation, or ``None`` for non-evidence lines.

    Empty-content evidence lines are KEPT (floored excerpt), intentionally
    preferring provenance retention over the research brief's "drop" advisory.
    """
    if not isinstance(line, dict):
        return None
    kind = line.get("type")
    kind = kind if isinstance(kind, str) else "unknown"
    if kind not in _EVIDENCE_TYPES:
        return None
    ref = str(line.get("uuid") or line.get("sessionId") or "claude-code:unknown")
    ts = line.get("timestamp")  # transcript ts is an ISO str; history.jsonl is epoch-ms int
    msg_raw = line.get("message")
    msg = msg_raw if isinstance(msg_raw, dict) else {}
    return Observation(
        source_ref=SourceRef(source_id="claude-code", ref=ref, kind=kind),
        excerpt=_line_excerpt(line, kind, ref),
        mode=SourceMode.PASSIVE,
        author="claude" if kind == "assistant" else ("user" if kind == "user" else "claude-code"),
        timestamp=ts if isinstance(ts, str) else "",
        metadata={
            "session_id": str(line.get("sessionId") or ""),
            "cwd": str(line.get("cwd") or ""),
            "model": str(msg.get("model") or ""),
            "line_type": kind,
        },
    )


class ClaudeCodeConnector:
    """Claude Code connector identity plus the transcript-line parse surface.

    Trust tier T0 (file import). The live file-watch path is deferred; this is
    the parse surface. ``observations`` accepts a single line dict or a
    ``{"lines": [...]}`` batch and drops non-evidence lines.
    """

    source_id = "claude-code"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.PASSIVE}))

    def observations(self, payload: dict) -> list[Observation]:
        raw_lines = payload.get("lines")
        lines: Iterable = raw_lines if isinstance(raw_lines, list) else [payload]
        return [obs for obs in (parse_session_line(line) for line in lines) if obs is not None]
