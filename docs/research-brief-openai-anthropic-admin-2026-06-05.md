# Research Brief

**Date**: 2026-06-05
**Analyst**: The Qor-logic Analyst
**Target**: OpenAI Admin (audit logs) API + Anthropic Admin (usage/cost) API — connectivity for read-only evidence connectors
**Scope**: Auth, response payload schemas, webhook/MCP availability, and the PII shape of each — to ground the `openai_admin` + `anthropic_admin` connectors before build.

---

## Executive Summary

The two AI-vendor admin APIs complete the AI-leverage evidence set alongside Copilot/Cursor/Devin, and split cleanly by evidence type: **OpenAI's audit-logs API is governance/security evidence** (who did what — key lifecycle, project changes, logins) and is **actor-PII-heavy** (user email, IP) → drop actor identity at parse; **Anthropic's Usage & Cost API is leverage evidence** (tokens/cost by workspace/model/tier) and is **aggregate, PII-free** (opaque ids only). Both are poll-only REST with org-admin keys; no webhooks, no first-party evidence MCP. No blocking blueprint drift — both fit the parse-surface + poll-harness pattern, and the redaction-and-pass model (Entry #79) is available for any residual free-text.

## Findings

### Interface: OpenAI Admin — audit logs
- **Endpoint**: `GET /v1/organization/audit_logs`. Source: [OpenAI API Reference — audit logs](https://platform.openai.com/docs/api-reference/audit-logs/list), [Admin APIs guide](https://developers.openai.com/api/docs/guides/admin-apis).
- **Auth**: **Bearer Admin API key** (`Authorization: Bearer $OPENAI_ADMIN_KEY`; Org-Owner-only; admin keys cannot call non-admin endpoints). Org must enable logging in Data Controls (irreversible once on).
- **Response** (`{data: [event]}`), each event: `id`, `effective_at` (unix s), `type` (57 values: `api_key.created/updated/deleted`, `login.succeeded/failed`, `logout.*`, `project.created/updated/archived/deleted`, `role.*`, `user.added/updated/deleted`, `invite.*`, `organization.updated`, …), `project` (id/name), `actor` (`session{ip_address, user{id,email}}` or `api_key{user{id,email}|service_account{id}}`), and a per-`type` detail object.
- **PII**: **actor-heavy** — `actor.session.user.email`, `actor.api_key.user.email`, `actor.session.ip_address`, user ids.
- **Pagination**: cursor (`limit` 1-100, `after`/`before`); filters `event_types`, `effective_at` gt/gte/lt/lte, `project_ids`, `actor_ids`/`actor_emails`. **Poll-only, no webhooks.**

### Interface: Anthropic Admin — usage & cost
- **Endpoints**: `GET /v1/organizations/usage_report/messages` (token usage) + `GET /v1/organizations/cost_report` (USD cost). Source: [Anthropic Usage & Cost API](https://platform.claude.com/docs/en/api/usage-cost-api).
- **Auth**: `x-api-key: $ANTHROPIC_ADMIN_KEY` (admin key, `sk-ant-admin…`, admin-role-only) + `anthropic-version: 2023-06-01`.
- **Response**: time-bucketed records (`bucket_width` `1m`/`1h`/`1d`; `starting_at`/`ending_at`) grouped by `workspace_id` / `api_key_id` / `model` / `service_tier` (and `inference_geo`, `speed` beta), with token metrics (uncached_input, cached input, cache_creation, output) and cost (USD cents, decimal strings). `workspace_id`/`api_key_id` may be `null` (default workspace / Workbench).
- **PII**: **none** — grouping dimensions are opaque ids (`wrkspc_…`, `apikey_…`), model names, tiers; no user email/name. Per-user cost is a SEPARATE [Claude Code Analytics API](https://platform.claude.com/docs/en/manage-claude/claude-code-analytics-api) (per-user PII) → **deferred**.
- **Pagination**: `has_more` + `next_page`; poll ≤ once/min. **Poll-only, no webhooks.**

### MCP relevance (SG-K)
No first-party evidence MCP for either admin surface. Read-only evidence uses the official admin REST API directly; MCP is the interactive-steering edge case (`bicameral-mcp`). Connectivity path = REST poll for both.

## Blueprint Alignment

| Blueprint claim | Actual finding | Status |
|---|---|---|
| Catalog shortlist: "OpenAI Admin/Audit + Anthropic Admin (P1)" | Confirmed — both are org-admin-key REST poll APIs | MATCH |
| Connector pattern: `parse_*(payload)->Observation`, `deliver_poll`→`observations`, read-only (ADR-0008) | Both fit — active poll, no webhook/`verify()`, like `osv`/`copilot` | MATCH |
| PII handling: FX-SEC-001 (reject) + redact-and-pass (Entry #79) | OpenAI audit actor = structured identity → **drop at parse** (ServiceNow `caller_id` precedent); Anthropic = aggregate PII-free (Copilot precedent); `redact()` available for free-text event details | MATCH |

## Recommendations

1. **(P1) OpenAI Admin connector** — `parse_audit_log(event)`: excerpt = event `type` + project + `effective_at` (governance evidence); **drop `actor` identity** (`email`/`ip_address`/`user.id` never read); run any free-text per-event detail through `redact()`. `event.id`→ref, `kind="audit_event"`. Active poll; Bearer admin key + cursor pagination deferred.
2. **(P1) Anthropic Admin connector** — `parse_usage(record)`: excerpt = token/cost metrics by model/workspace/tier (aggregate, PII-free); `kind="usage_metrics"`. Active poll; `x-api-key` admin key + `has_more`/`next_page` + `anthropic-version` header deferred. Per-user Claude Code Analytics API deferred (PII).
3. **(LOW)** Neither ships `verify()` (poll-only, no webhook); prove Beta via `deliver_poll`.

## Updated Knowledge

To `docs/SHADOW_GENOME.md` (connector pattern note): AI-vendor admin APIs split by evidence type — **audit logs = governance evidence, actor-PII-heavy → drop actor identity at parse** (structured identity, like ServiceNow `caller_id`); **usage/cost = leverage evidence, aggregate PII-free → parse directly** (like Copilot). Per-user cost/analytics surfaces are a separate, PII-bearing API deferred behind the redact-and-pass model.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
