# Claude Code Auth

Auth model recorded for the live cycle; this connector ships the **parse
surface** only.

- Default trust tier: T0 (local file import).
- Auth: none (reads local JSONL the operator already has on disk).

## Deferred live paths

- File-watch of `~/.claude/projects/<project-slug>/<session-id>.jsonl` (30-day
  default retention; `cleanupPeriodDays`).
- Global prompt log `~/.claude/history.jsonl` (note: its `timestamp` is **epoch
  milliseconds**, unlike the transcript's ISO string — must not be conflated).
- Git-attribution path (`Co-Authored-By: Claude <noreply@anthropic.com>`,
  default-on but **suppressed in this repo** per stealth policy, so it would
  miss our own Claude commits — lower value than the transcript path).

**Schema note (verified 2026-06-08, code.claude.com/docs):** the file **paths** and
30-day retention ARE officially documented, but the per-line transcript **field schema**
(`type`/`uuid`/`sessionId`/`message.content` blocks/`cwd`/`model`) and the `history.jsonl`
epoch-ms vs transcript-ISO timestamp distinction are **observed/undocumented** (DOC-SILENT) —
the parse rests on observed structure, not a published schema. Pin against a captured real
transcript before relying on the line shape at Live.

## Sensitivity

Transcripts are plaintext on disk and contain file contents, command
stdout/stderr, and pasted text — i.e. potential secrets/PII. The producer
sensitive screen (`adapter/core/sensitive.py`, `FX-SEC-001`) is the in-pipeline
guard; this connector performs no redaction of its own.

No credentials are stored in this package. See [references.md](references.md)
and [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
