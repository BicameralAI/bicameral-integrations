# Research Brief — Fathom + Claude Code connectors (flip-readiness foundation)

**Date**: 2026-06-12
**Analyst**: The Qor-logic Analyst
**Target**: the `fathom` and `claude_code` Beta connectors — next in queue for live/flip hardening + purple-team.
**Scope**: verify-before-cite each source contract against the LIVE source (SG-2026-06-12-A), assess each against the flip-ready standard (FX-CFG-001 descriptor + references.md/auth.md exceeding the minimum, PII handling, security), and recommend the `/qor-auto-dev-1` scope.

---

## Executive Summary

Both connectors are sound Beta parse surfaces with above-average local docs, but **neither is flip-ready** — each has a concrete **PII gap** (no redact-and-pass on PII-dense free text) and **no FX-CFG-001 descriptor**, and each has a contract finding that verify-before-cite surfaced:

- **Fathom** — the provider contract **re-verifies clean against live docs (2026-06-12)**; every parsed field matches. But the connector **injects `speaker.display_name` (real names) into every transcript line and emits the transcript un-redacted** — which both leaks email/phone past the hard screen AND **contradicts the platform's now-public "human real names are dropped" guarantee** (README / capability matrix).
- **Claude Code** — verify-before-cite against a **real 6,008-line transcript** found **schema drift**: the documented `{user, assistant, summary}` model is partly stale (no `summary` type in the current format; new `ai-title` / `pr-link` / `system` types). The connector's defensive skip-unknown design means it does not crash, but it parses a now-absent type and misses new evidence; and the **arbitrary-plaintext transcript is emitted un-redacted** (highest-risk free text in the catalog) with `cwd` leaking the OS username.

Both need a focused `/qor-auto-dev-1` flip cycle: **redact-and-pass + identity handling + FX-CFG-001 descriptor + doc refresh + purple-team**, sequenced one connector at a time.

## Findings

### Fathom — provider contract (verified live 2026-06-12)

Sources: `developers.fathom.ai/webhooks` + `developers.fathom.ai/api-reference/meetings/list-meetings`.

| Contract element | Connector / `auth.md` claim | Live source | Status |
|---|---|---|---|
| Webhook headers | `webhook-id`, `webhook-timestamp` (epoch s), `webhook-signature` (`v1,<b64>`) | identical | **MATCH** |
| Secret + signed content | `whsec_` base64-decoded; HMAC-SHA256(secret, `{id}.{timestamp}.{body}`), base64, constant-time | identical | **MATCH** |
| "Svix"/"Standard Webhooks" brand | inferred (not provider-named) | docs still do **not** name Svix | **MATCH** (inference correct) |
| Replay window | `auth.md`: "300 s is the Standard-Webhooks default, **not Fathom-documented**" | docs now state **"within 5 minutes"** | **DRIFT (doc)** — now Fathom-documented; update the note |
| REST auth header | `auth.md`: "API key sent on each request" (header unnamed) | header is **`X-Api-Key`** | **DRIFT (doc gap)** — name it |
| Meeting fields | `recording_id`, `meeting_title`/`title`, `transcript[].speaker.display_name`, `transcript[].text`, `default_summary.markdown_formatted`, `share_url`, `recorded_by.name`, `recording_end_time` | identical (verbatim) | **MATCH** |
| Base URL / endpoint | `https://api.fathom.ai/external/v1` · `GET /meetings`, cursor pagination | identical | **MATCH** |

- **`connectors/fathom/connector.py:28-44` `_flatten_transcript`** builds `"<speaker.display_name>: <text>"` lines; **`:56` `parse_meeting`** sets `excerpt = flattened transcript (un-redacted)`, fallback summary → title. `:67` `author=""` (real-name `recorded_by.name` already dropped, #150). **No `redact()` anywhere.**
- **PII gap (HIGH for flip):** the transcript carries spoken content (email/phone/secret/PHI/PAN possible) AND `speaker.display_name` real names — `FX-SEC-001` hard-rejects secret/PHI/PAN but NOT generic email/phone/name. This matches the granola pre-flip gap (#149/#150 class).

### Claude Code — source contract (verified against a real transcript 2026-06-12)

Source: a real local session transcript (6,008 lines), keys-only inspection; cross-checked vs `code.claude.com/docs`.

- **Real `type` values observed:** `user`, `assistant`, `system`, `attachment`, `mode`, `permission-mode`, `file-history-snapshot`, `last-prompt`, `ai-title`, `queue-operation`, `pr-link`. **There is NO `summary` type** in the current format.
- **`connectors/claude_code/connector.py:27` `_EVIDENCE_TYPES = {user, assistant, summary}`** — `summary` is now absent from the live schema (legacy/older-version type); `:70-73` reads `line.get("summary")` which the current format never carries. **DRIFT (stale type).**
- **New evidence-bearing types not handled:** `ai-title` (`aiTitle` — the current session-summary surface), `pr-link` (`prNumber`/`prRepository`/`prUrl` — useful provenance). Neither errors (skip-unknown is correct, SG-2026-06-04-I) but both are missed evidence.
- **MATCH:** content block types `text` / `thinking` / `tool_use` / `tool_result` (`:46-55` handles text/tool_use/tool_result, skips thinking) ✓; metadata `cwd` / `model` / `sessionId` (`:99-104`) all present on the real lines ✓; `uuid`/`timestamp` (ISO str) ✓.
- **PII gap (HIGH for flip):** `:95` `excerpt` is raw transcript text with **no `redact()`** — Claude Code transcripts are the highest-risk free text in the catalog (pasted secrets, file contents, command stdout/stderr). `FX-SEC-001` hard-rejects secret/PHI/PAN (good) but email/phone/name pass. `:101` `cwd` is emitted in metadata and on a typical install is `C:\Users\<name>\…` / `/Users/<name>/…` — **leaks the OS username**.

## Blueprint Alignment

| Blueprint / platform claim | Actual finding | Status |
|---|---|---|
| Flip-ready connectors carry an FX-CFG-001 descriptor (config.json) | neither fathom nor claude_code has one | **DRIFT** → build in flip cycle |
| PII-dense free-text bodies are redact-and-passed before emit (granola/devin/slack standard) | fathom transcript + claude_code excerpt are emitted un-redacted | **DRIFT (HIGH)** → add redact-and-pass |
| "Human real names are dropped; only pseudonymous identity surfaced" (README / capability matrix) | fathom injects `speaker.display_name` real names into every transcript line | **DRIFT (HIGH)** → drop/pseudonymize |
| A connector's documented schema is verified-before-cite | claude_code line schema drifted (`summary` gone; new types) | **DRIFT** → re-pin to the verified shape |

## Recommendations (sequenced `/qor-auto-dev-1` scope; documentation must EXCEED the minimum)

1. **Fathom flip cycle (P1):** (a) redact-and-pass the flattened transcript + summary + title (`redact()` like granola); (b) **drop/pseudonymize `speaker.display_name`** to honor the "real names dropped" guarantee (recommend: emit bare spoken text, or a generic `Speaker:` label — confirm with the Governor whether transcript attribution is worth an accepted-risk exception); (c) author the FX-CFG-001 descriptor (modes `["passive","webhook"]`; credentials = API key `X-Api-Key` + `whsec_` webhook secret; webhook block `new-meeting-content-ready`, Svix-style sig, 5-min replay); (d) refresh `auth.md`/`references.md` (name `X-Api-Key`; 5-min window now Fathom-documented; PII posture = redact-and-pass + names dropped). **Confidence: high** (contract fully verified live).
2. **Claude Code flip cycle (P0):** (a) redact-and-pass the excerpt; (b) sanitize/scrub `cwd` so it cannot carry an OS username (or drop it from wire metadata); (c) re-pin the documented schema to the verified-against-real-transcript reality — keep `summary` as legacy-tolerant, and decide whether to ADD `ai-title` (new summary surface) and `pr-link` (provenance) as evidence; (d) author the FX-CFG-001 descriptor (modes `["passive"]`; **credentials `[]`** — local file, no auth; data block stating the redact-and-pass posture + the FX-SEC-001 hard gate as the secret backstop); (e) refresh `references.md`/`auth.md` with the verified line schema + the cwd-username note. **Confidence: high** (schema pinned against a live transcript).
3. **Both:** run the connector purple-team attack classes (SSRF/host-pin is N/A for fathom's operator-poll + claude_code's local file; the live classes are **parse-robustness, PII-on-wire, replay/dedup (fathom), and redact-completeness**) after the flip, per the established bar.

## Updated Knowledge (Shadow Genome)

- **SG-2026-06-12-G** — *verify a local/desktop source's line schema against a REAL captured artifact, not the vendor doc.* Claude Code's published docs cover file paths + retention but are DOC-SILENT on the per-line field schema; a real 6,008-line transcript showed the documented `summary` type is gone and new types (`ai-title`, `pr-link`) exist. For file-import connectors, pin against a current real file every flip cycle.
- **SG-2026-06-12-H** — *a connector that INJECTS a structured real-name field (e.g. `speaker.display_name`) violates the "real names dropped" guarantee even when its `author` is dropped.* Redact-and-pass scrubs email/phone but not a deliberately-prefixed display name; identity minimization must cover injected structured names, not just the `author` slot.

---

_Research complete. Both source contracts verified live; two flip cycles scoped (fathom P1, claude_code P0), each requiring redact-and-pass + identity handling + an FX-CFG-001 descriptor + doc refresh exceeding the minimum, then purple-team. Findings are advisory — implementation decisions remain with the Governor._
