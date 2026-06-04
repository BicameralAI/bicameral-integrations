# Research Brief

**Date**: 2026-06-04
**Analyst**: The Qor-logic Analyst
**Target**: Implement the **Claude Code** connector — passive ingest of session-transcript JSONL lines as provider-neutral Observations.
**Scope**: `parse_session_line(line) -> Observation | None` + `ClaudeCodeConnector`; live file-watch deferred. Grounded against official docs (code.claude.com) + direct on-disk inspection of live transcripts (CLI 2.1.160). Tagged verified/uncertain.

---

## Executive Summary

Claude Code writes session transcripts as **local JSONL** at `~/.claude/projects/<project-slug>/<session-id>.jsonl` (plaintext, 30-day default retention). It is a **heterogeneous append-only event log**, not a uniform message stream — `type` ∈ {`user`, `assistant`, `summary`, `system`, `mode`, `permission-mode`, `file-history-snapshot`, `attachment`, `last-prompt`, …}. Only `user`/`assistant`/`summary` carry evidence. The format is **documented-but-unversioned at the line level** (only a CLI `version` field), so the parser must be a *filtering, defensively-typed* line parser that skips unknown/meta lines rather than crashing (SG-2026-06-04-I is the dominant risk). P0, passive file import, **T0**. Maps to the existing seam with zero contract change. Transcripts carry file contents/secrets/PII → the producer sensitive screen (`FX-SEC-001`) is the guard; the connector does NOT self-redact.

## Findings

### F1 — Transcript JSONL line schema (verified by inspection, CLI 2.1.160)
Per-line envelope (message/attachment lines): `parentUuid` (nullable), `isSidechain`, `uuid`, `timestamp` (ISO-8601 string), `sessionId`, `cwd`, `version`, `gitBranch`, `userType`, `type`. **Assistant** lines: `message` = raw Anthropic message object; text in `message.content[]` blocks (`thinking`/`text`/`tool_use`); a single turn is **split across multiple lines** sharing `message.id`. **User** lines: `message.content` is **either a str** (prompt) **or a list** (incl. `tool_result` blocks); tool results also duplicate a top-level `toolUseResult`. **summary** line: `{type:"summary", summary, leafUuid}` (rare; the resume pointer observed is actually `type:"last-prompt"`).

### F2 — Non-evidence line types (filter → None)
`mode`, `permission-mode`, `file-history-snapshot`, `attachment`, `last-prompt`, and any unknown future `type` → return `None`. Assistant lines whose only block is empty `thinking` → `None`. This keeps each emitted Observation a real piece of evidence with `ref = uuid`.

### F3 — `~/.claude/history.jsonl` (verified)
Flat global prompt log: `{display, pastedContents, timestamp (epoch ms int), project}`. Different time format (int ms) from transcripts (ISO str) — **do not feed the int into the str timestamp**. Out of scope for v1 (transcript lines are richer); noted for a future mode.

### F4 — Commit attribution (verified)
`includeCoAuthoredBy` defaults true (`Co-Authored-By: Claude <noreply@anthropic.com>`), now superseded by `attribution`. **This repo strips it (stealth memory)** → a git-attribution path would miss our own Claude commits, so the **transcript path is the higher-value surface**; git-attribution is deferred/optional.

### F5 — Mapping (parse_session_line)
`source_id="claude-code"`; `ref = uuid or sessionId or "claude-code:unknown"`; `url=""`; `kind = type` (str-guarded else "unknown"); `mode=PASSIVE`; `author` = role-derived (`assistant`→"claude", `user`→"user", `summary`→"claude-code"); `timestamp` = `timestamp` only if str; `metadata = {sessionId, cwd, model, parentUuid, line_type, is_sidechain}` (each guarded `.get`). **Excerpt** (ordered, guarded): `message.content` str → use; list → concat (`text`→text, `tool_use`→`[tool_use:name] …`, `tool_result`→stringified, skip empty `thinking`); `summary` → summary text; **terminal floor** `f"[claude-code:{kind}] {ref}"` (SG-2026-06-04-G) so excerpt is never blank.

### F6 — Contract fit + safety
Read-only parse → Observation → normalize() (zero contract change). Transcripts carry secrets/PII → `pipeline._screen_sensitive` HARD-gates; the connector must not redact itself. Section 4 Razor: a filtering parser with a guarded excerpt-extractor helper stays ≤40 lines/fn, ≤3 nesting.

## Blueprint Alignment

| Claim | Finding | Status |
|---|---|---|
| Claude Code P0, T0 passive file (value-add Entry #35) | local JSONL transcripts; no API dependency | MATCH |
| Defend wrong-typed/absent (SG-I) | heterogeneous unversioned log → filter+guard | MATCH (dominant risk) |
| Terminal excerpt floor (SG-G) | `[claude-code:{kind}] {ref}` floor | MATCH |
| Interactivity test (SG-K) | passive evidence ingest, not agent action → adapter | MATCH |
| Sensitive screen is the guard | transcripts carry secrets → FX-SEC-001 | MATCH |

No DRIFT.

## Recommendations
1. **[P0] `/qor-plan` at L2** — `parse_session_line(line: dict) -> Observation | None` (filter non-evidence types) + `_line_excerpt` helper + `ClaudeCodeConnector.observations(lines)` mapping + dropping `None`s; synthetic JSONL fixture (user / assistant-with-tool_use / summary + adversarial empty-content + meta line); behavioral tests incl. terminal floor, None-filtering, wrong-typed defense, end-to-end normalize().
2. **[P1] Defer** live file-watch + `history.jsonl` + git-attribution path — record in `auth.md`.
3. **[P2] Fixture** strictly synthetic (no real paths/secrets).

## Updated Knowledge
SHADOW_GENOME (proposed) **SG-2026-06-04-L**: a connector over an *undocumented heterogeneous event log* (Claude Code transcript JSONL) must be a **filtering** parser — unknown/meta `type` → skip (`None`), not error; one line ≠ one message (assistant turns split per content block); and a sibling time format (`history.jsonl` epoch-ms) must never leak into the ISO-string timestamp. Extends SG-2026-06-04-I to the "skip-don't-crash on unknown record kinds" case.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
