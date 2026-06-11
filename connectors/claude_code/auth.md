# Claude Code Auth

Auth model recorded for the live cycle; this connector ships the **parse
surface** only.

- Default trust tier: T0 (local file import).
- Auth: none (reads local JSONL the operator already has on disk).
- `source_id`: **`claude_code`** (underscore) — aligned to the folder for the FX-CFG-001
  descriptor (renamed from the prior `claude-code`, 2026-06-12 flip cycle).

## Deferred live paths

- File-watch of `~/.claude/projects/<project-slug>/<session-id>.jsonl` (30-day
  default retention; `cleanupPeriodDays`).
- Global prompt log `~/.claude/history.jsonl` (note: its `timestamp` is **epoch
  milliseconds**, unlike the transcript's ISO string — must not be conflated).
- Git-attribution path (`Co-Authored-By: Claude <noreply@anthropic.com>`,
  default-on but **suppressed in this repo** per stealth policy, so it would
  miss our own Claude commits — lower value than the transcript path).

**Schema note (DOC-SILENT; re-pinned against a REAL transcript 2026-06-12, SG-2026-06-12-G):**
the file **paths** + 30-day retention are officially documented, but the per-line **field schema**
is observed/undocumented. A real 6,008-line transcript confirms: evidence types `user`/`assistant`
carry `message.content` (block types `text`/`thinking`/`tool_use`/`tool_result`); `cwd`/`model`/
`sessionId`/`uuid`/`timestamp` (ISO str) are present. The documented `summary` type is **absent in
the current format** (kept as legacy-tolerant); new types `ai-title` (session summary now),
`pr-link`, `system`, `queue-operation` exist and are **intentionally not emitted** this cycle (the
user/assistant turns are the evidence surface). `history.jsonl` `timestamp` is epoch-ms (not the
transcript's ISO) — never conflate. Re-pin against a current transcript each flip cycle.

## Sensitivity

Transcripts are plaintext on disk and contain file contents, command stdout/stderr, and pasted text
— i.e. potential secrets/PII. The connector now (2026-06-12 flip cycle):

- **redact-and-passes** the excerpt content (secret/PHI/PAN + email/phone scrubbed); the
  `[claude_code:kind] <uuid>` floor literal is left un-redacted so an opaque uuid is not
  mis-scrubbed. `FX-SEC-001` (`adapter/core/sensitive.py`) hard-rejects any residual secret/PHI/PAN.
- **home-prefix-scrubs `cwd`** (`C:\Users\<name>\…` / `/Users/<name>/…` / `/home/<name>/…` → `~/…`)
  so the OS username does not leak on the wire.

No credentials are stored in this package. See [references.md](references.md)
and [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
