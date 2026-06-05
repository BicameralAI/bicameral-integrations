# Research Brief

**Date**: 2026-06-05
**Analyst**: The Qor-logic Analyst
**Target**: GitHub Copilot usage-metrics API + Cursor Admin API — connectivity (API / webhook / MCP) for read-only evidence connectors
**Scope**: Authentication, response payload schemas, webhook availability, MCP relevance, and the PII surface of each — to ground the `copilot` + `cursor` connectors before build.

---

## Executive Summary

Both GitHub Copilot and Cursor expose **poll-only REST APIs** (no webhooks, no first-party evidence MCP) for usage telemetry. **Copilot's aggregate metrics endpoint is PII-free by design**; **Cursor's daily-usage endpoint is PII-dense** — every row carries `email` and `name`. The single most important finding (which corrects a prior assumption) is that **FX-SEC-001 screens secret / PHI / PAN only and does NOT detect a generic email**, so it provides **no backstop** for Cursor PII — the connector must drop identity fields at parse time as the sole control. No blocking drift against the connector blueprint; both fit the existing parse-surface + poll-harness pattern.

## Findings

### Interface: GitHub Copilot metrics API
- **Endpoint**: `GET /orgs/{org}/copilot/metrics` (also `/enterprises/{ent}/...` and team scopes). Source: [GitHub Docs — REST API endpoints for Copilot metrics](https://docs.github.com/en/rest/copilot/copilot-metrics).
- **Auth**: OAuth app token / PAT with `manage_billing:copilot` **or** `read:org` / `read:enterprise`.
- **Response shape** (daily array; each object):
  - `date` (date), `total_active_users` (int), `total_engaged_users` (int)
  - `copilot_ide_code_completions` → `total_engaged_users`, `languages[]{name,total_engaged_users}`, `editors[]{name,total_engaged_users,models[]}`
  - `copilot_ide_chat` → `editors[]{models[]{total_chats,total_chat_insertion_events,total_chat_copy_events}}`
  - `copilot_dotcom_chat` → `models[]{name,total_engaged_users,total_chats}`
  - `copilot_dotcom_pull_requests` → `repositories[]{name,total_engaged_users,total_pr_summaries_created}`
- **PII**: **None** — aggregate counts only, no per-developer identity. Confirmed against the documented schema.
- **Webhooks**: None for this data (outbound poll only).
- **Note**: the **legacy Copilot "usage" API was closed 2026-04-02**; the newer per-user NDJSON "usage metrics" *report* API (signed download URLs) DOES carry per-user PII → deferred.

### Interface: Cursor Admin API
- **Endpoint**: `POST /teams/daily-usage-data` (date range; ≤ hourly poll). Companion read endpoints: `GET /teams/members`, `POST /teams/spend`. Source: [Cursor Docs — Admin API](https://cursor.com/docs/account/teams/admin-api).
- **Auth**: HTTP Basic — **API key as username, empty password** (`-u YOUR_API_KEY:`). Team-admin-issued key.
- **Response shape** (`daily-usage-data`, per-user-day rows): `userId`, `day`, `date`, **`email`**, **`name`** (via members/spend), `isActive`, `totalLinesAdded`, `acceptedLinesAdded`, `totalApplies`, `totalAccepts`, `totalRejects`, `totalTabsShown`, `totalTabsAccepted`, `composerRequests`, `chatRequests`, `agentRequests`, `cmdkUsages`, `mostUsedModel`, `clientVersion`, …
- **PII**: **Dense** — `email` is present in **every** daily-usage row; `name` in members/spend rows.
- **Webhooks**: None (poll-only, documented "poll at most once per hour").

### MCP relevance (SG-K interactivity test)
- No **first-party** evidence MCP for either provider. A third-party `cursor-usage` MCP server exists (wraps the Cursor API) but is an interactive/agentic surface. Per SG-K, **read-only evidence ingestion uses the official API directly**; MCP is the edge case for interactive steering (that is `bicameral-mcp`'s domain, not an evidence adapter). Connectivity path for both = REST poll.

## Blueprint Alignment

| Blueprint claim | Actual finding | Status |
|---|---|---|
| Catalog: Copilot P1, "read-only usage-metrics endpoints (post-2026-04 set); per-user data is PII; needs admin permission" | Confirmed — aggregate `/copilot/metrics` is PII-free; legacy API closed 2026-04-02; per-user report API is PII (deferred) | MATCH |
| Catalog: Cursor P1, "read-only Admin API (read endpoints only); verify Privacy-Mode effect; admin-only key custody" | Confirmed — basic-auth admin key; daily-usage rows are PII-dense (`email`); poll-only | MATCH |
| Connector pattern: `parse_*(payload)->Observation` + poll via `deliver_poll`→`observations`; read-only (ADR-0008) | Both fit — active-poll, no webhook/`verify()`, like `osv`/`google_drive` | MATCH |
| Prior assumption: "FX-SEC-001 is a hard reject-on-PII screen" (would catch a leaked email) | **DRIFT** — `adapter/core/sensitive.py` screens secret/PHI/PAN only; the lone `email` token is `patient_email:` (PHI, label-adjacent). A bare email is NOT detected, and `_screen_sensitive` never scans `Observation.metadata` | **DRIFT** |

## Recommendations

1. **(HIGH) Cursor: drop identity at parse time as the SOLE PII control.** `parse_usage_day` must read a strict allowlist of non-PII aggregate fields (numeric metrics + `mostUsedModel`) and never read `email` / `name` / `userId` / `clientVersion`. Do **not** rely on FX-SEC-001 as a backstop — it does not detect generic email. Prove with a non-vacuous test (fixture contains email+name; assert absent from the whole Observation + the post-normalize emission).
2. **(MED) Copilot: parse the aggregate metrics object only.** Defer the per-user NDJSON report API behind a future PII redaction-and-pass model.
3. **(LOW) Both poll-only:** ship no `verify()`/`normalize_event()`; prove Beta via `deliver_poll`. Live REST poll + token/key custody deferred to the operator runtime (`auth.md`).

## Updated Knowledge

Added to `docs/SHADOW_GENOME.md`: **FX-SEC-001 is a secret/PHI/PAN screen, NOT a generic-PII/email screen** — connectors handling PII-dense sources (Cursor daily-usage, live Zendesk ticket bodies) must drop/redact PII at parse time; the emission screen is not a backstop, and it never scans `Observation.metadata`.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
