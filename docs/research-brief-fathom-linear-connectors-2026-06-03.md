# Research Brief

**Date**: 2026-06-03
**Analyst**: The Qor-logic Analyst
**Target**: Net-new source connectors for **Fathom** (meeting intelligence) and **Linear** (issue tracking) in `bicameral-integrations`; secondary confirmation of the three MCP-port connectors still pending (`google_drive`, `granola`, `local_directory`).
**Scope**: External API/webhook surface verification for Fathom + Linear, mapped onto the existing `adapter.core` Observation contract and the active/passive/webhook mode taxonomy (ADR-0006). Architecture decision for this cycle: ship a provider-neutral **parse surface** + fixtures + conformance tests; defer live network, credential resolution, and live signature verification. Sources: official vendor docs (developers.fathom.ai, linear.app/developers) and in-repo source (`file:line`).

---

## Executive Summary

Both providers are net-new builds, **not** ports — `bicameral-mcp` has no Fathom or Linear source (only stale `.pyc` for Linear's reserved package name; confirmed by `find sources events/sources webhooks -name "linear*.py"` → empty). SHADOW_GENOME **SG-2026-06-02-D** already records that Linear (with Jira/Notion/Slack) was *built then backed out* of MCP `dev` (`fbdd9ec`) precisely so this repo could own it — so Linear is expected, not speculative. Both APIs map cleanly onto the existing `Observation` → `normalize()` seam with **no contract changes required**: Fathom is a meeting/transcript source analogous to the Granola port (PASSIVE poll + WEBHOOK), Linear is an issue source whose richest entry point is the **webhook** event envelope (WEBHOOK + ACTIVE). No blocking contract gaps found — research-complete; cycle may proceed to `/qor-plan`. Two non-blocking security facts must be recorded for the live cycle (deferred this cycle): both providers use **HMAC-SHA256 webhook signing** (Fathom = Standard Webhooks/Svix; Linear = `Linear-Signature`), and both payloads carry **PII + meeting/issue content** that the producer-side sensitive screen (`FX-SEC-001`) is the correct guard for.

## Findings

### F1 — Fathom REST surface (PASSIVE poll source)
- **Base / auth**: `https://api.fathom.ai/external/v1`, API-key auth (key from Fathom settings). Rate limit **60 calls / 60 s**, surfaced via `RateLimit-Limit` / `RateLimit-Remaining` / `RateLimit-Reset` headers. Source: developers.fathom.ai/api-overview.
- **List**: `GET /meetings` — **cursor pagination** (`next_cursor` in response, `cursor` query param), time-window filters `created_after` / `created_before`, plus `recorded_by[]`, `teams[]`, `calendar_invitees_domains[]`, and opt-in expansions `include_transcript` / `include_summary` / `include_action_items` / `include_crm_matches` (all default `false`). Source: developers.fathom.ai/api-reference/meetings/list-meetings.
- **Meeting item shape** (the parse target): `title`, `meeting_title`, `recording_id` (int), `url`, `share_url`, `created_at`, `scheduled_start_time` / `scheduled_end_time`, `recording_start_time` / `recording_end_time`, `transcript_language`, `calendar_invitees[]{name,email,email_domain,is_external,matched_speaker_display_name}`, `recorded_by{name,email,email_domain,team}`, `transcript[]{speaker{display_name,matched_calendar_invitee_email},text,timestamp(HH:MM:SS)}`, `default_summary{template_name,markdown_formatted}`, `action_items[]{description,user_generated,completed,recording_timestamp,recording_playback_url,assignee{...}}`, `crm_matches{contacts,companies,deals}`.
- **Transcript**: `GET /recordings/{recording_id}/transcript` → `{transcript:[{speaker,text,timestamp}]}` (optional async `destination_url`).
- **Cursor parity**: maps to the passive contract's `cursor` (`PollingConnector.pull(config, cursor)` / `confirm()` in `adapter/core/contracts.py:42-52`) — same two-phase-commit watermark discipline as the Granola MCP poller.

### F2 — Fathom webhook surface (WEBHOOK source)
- **Event**: `new-meeting-content-ready`; the payload **is a meeting object** (same shape as F1 list items, optionally including `default_summary` / `transcript` / `action_items`). Source: developers.fathom.ai/webhooks.
- **Signing**: **Standard Webhooks / Svix** scheme — headers `webhook-id`, `webhook-timestamp` (epoch **seconds**), `webhook-signature` (base64, space-delimited versioned sigs). Secret prefixed `whsec_`; verify = `HMAC-SHA256(base64decode(secret), "${id}.${timestamp}.${body}")`, base64-encode, **constant-time** compare. (Deferred this cycle; recorded for the live cycle.)

### F3 — Linear surface (WEBHOOK primary, ACTIVE GraphQL secondary)
- **API**: GraphQL at `https://api.linear.app/graphql`; personal API key via `Authorization` header; webhooks configured in Settings > API (admin). Source: linear.app/developers, linear.app/docs/api-and-webhooks.
- **Webhook envelope** (the parse target): `action` (`create|update|remove`), `type` (`Issue|Comment|Project|Cycle|...`), `actor{id,type,name}`, `createdAt` (ISO), `data` (entity), `url`, `updatedFrom` (prior values, update only), `webhookId`, `webhookTimestamp` (UNIX **ms**), `organizationId`.
- **Issue `data`**: `id` (uuid), `identifier` (e.g. `PROJ-123`), `title`, `description`, `priority` (int), `state`, `team{id,name}`, `assignee{id,name}`, `url`.
- **Signing**: `Linear-Signature` header = **hex** HMAC-SHA256 of the **raw** request body using the webhook signing secret. **Anti-replay**: reject when `abs(now − webhookTimestamp) > 60000 ms`. (Deferred this cycle; recorded for the live cycle.)

### F4 — Mapping onto the existing Observation contract (no contract change)
- `Observation` (`adapter/core/observations.py`) fields `source_ref` / `excerpt` / `mode` / `title` / `author` / `timestamp` absorb both providers:
  - **Fathom meeting** → `excerpt` = transcript text (or `default_summary.markdown_formatted`, or `meeting_title`); `title` = `meeting_title`/`title`; `author` = `recorded_by.name`; `timestamp` = `recording_end_time`/`created_at`; `source_ref{source_id:"fathom",ref:str(recording_id),url:share_url,kind:"meeting"}`; `mode` = PASSIVE (poll) / WEBHOOK.
  - **Linear issue event** → `excerpt` = `data.description` (fallback `title`); `title` = `[identifier] title`; `author` = `actor.name`; `timestamp` = `createdAt`; `source_ref{source_id:"linear",ref:identifier,url:data.url,kind:type.lower()}`; `mode` = WEBHOOK / ACTIVE.
- `normalize()` (`adapter/core/pipeline.py:71`) already produces a contract-valid `AdapterEmission` from any `Observation`; both connectors are pure parse surfaces, exactly like `connectors/github/connector.py` (`FX-GH-001`).

### F5 — Reuse, don't reinvent (SHADOW_GENOME alignment)
- **SG-2026-06-02-E**: bot's `CaptureMethod {ApiPoll, Webhook, Manual, AgentExtract}` and `SourceFreshness` enums are the downstream discriminators for ADR-0006 modes — connectors should keep `SourceMode` values aligned (already do).
- **SG-2026-06-02-D**: Linear was backed out of MCP for this repo; no live Linear code survives to port, so this is a clean-room build from the public webhook contract above.

### F6 — MCP-port connectors (secondary scope) — confirmed ready
- `google_drive` (active doc parse), `granola` (passive transcript), `local_directory` (passive file) were fully reviewed from `bicameral-mcp` source in this session. All three map onto `Observation` the same way GitHub does; `google_drive` already has an (ungoverned) draft to be plan-derived and legitimized this cycle. No external research outstanding.

## Blueprint Alignment

| Blueprint claim | Actual finding | Status |
|---|---|---|
| Source adapters consume "Jira, Linear, Slack, Notion, GitHub, email, **meetings**…" (`ARCHITECTURE_PLAN.md:33`) | Fathom = meetings, Linear = issues — both explicitly in the named source set | MATCH |
| Adapter output emits to gateway only; never writes canonical state (`ARCHITECTURE_PLAN.md:35`) | Both connectors are read-only parse surfaces → `Observation` → `normalize()`; no write path | MATCH |
| Active/passive/webhook modes (ADR-0006) | Fathom = PASSIVE+WEBHOOK; Linear = WEBHOOK+ACTIVE; `SourceMode` enum already covers all | MATCH |
| `Observation`/`AdapterEmission` contract is provider-agnostic (`adapter/core/*`) | Both providers fit existing fields with no schema change | MATCH |
| Webhook verify/dedup deferred until live (HIGH-2, security brief) | Both providers use HMAC-SHA256 signing; deferral consistent — must inherit mcp HMAC+dedup when live | MATCH (deferred) |
| Producer sensitive screen is the PII guard (`FX-SEC-001`) | Fathom/Linear payloads carry emails, names, meeting/issue content — screen applies at `validate_emissions` | MATCH |

No DRIFT detected.

## Recommendations

1. **[P1] Proceed to `/qor-plan`** — scope: `fathom` + `linear` connectors (parse surface + fixtures + conformance tests), plus finishing `granola` + `local_directory` ports and legitimizing the `google_drive` draft. One L2 feature cycle.
2. **[P1] Defer all live network + signature verification** — declare modes in `SourceCapabilities`, ship parse surfaces only (github precedent). Capture the HMAC schemes (F2, F3) in each connector's `auth.md` so the live cycle inherits them.
3. **[P2] Keep `source_id` values `fathom` / `linear`** — both satisfy `_SOURCE_ID_RE` (`pipeline.py:13`) and align with the bot `CaptureMethod` discriminator (SG-E).
4. **[P2] Fixtures must be PII-safe** — use synthetic names/emails on non-real domains so the `FX-SEC-001` sensitive screen and TruffleHog stay green.
5. **[P3] Linear webhook fixture should be an `Issue` `create` event**; Fathom fixture a `new-meeting-content-ready` meeting with a short synthetic `transcript`.

## Updated Knowledge

New entries appended to `docs/SHADOW_GENOME.md`: **SG-2026-06-03-A** (Fathom = Standard Webhooks/Svix `${id}.${timestamp}.${body}` HMAC; epoch-seconds timestamp) and **SG-2026-06-03-B** (Linear `Linear-Signature` hex HMAC over raw body, `webhookTimestamp` ms, 60 s anti-replay; webhook envelope `action/type/data/updatedFrom` is the richest ingest point — richer than a GraphQL poll).

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
