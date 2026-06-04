# Research Brief: CS / Support / Sales stakeholder-insight connectors

**Date**: 2026-06-04
**Phase**: RESEARCH (candidate evaluation — no build)
**Scope**: Evaluate **Zendesk, ServiceNow, ChurnZero, Gainsight** as read-only evidence connectors to extend Bicameral's visibility beyond developer tooling into support, sales, and customer-success stakeholder insight.

## Framework applied

- **Connector model**: read-only `parse_*(payload) -> Observation`; never writes canonical state or acts (ADR-0008).
- **Surface-selection / interactivity test (SG-2026-06-04-K)**: read-only evidence → direct API/webhook adapter in THIS repo (T0/T1); interactive agent action → `bicameral-mcp` (T3/T5). Default to the evidence adapter.
- **Preferred pattern**: a first-class *signed outbound webhook* (push — real-time evidence a poll can't get; deterministic + hash-chainable) is what Fathom/Linear/Sentry/PagerDuty/GitHub/Slack/Notion are built around. Poll-only is lower-leverage.
- **Bar**: official versioned read API and/or signed webhooks; stable evidence surface; operator-holdable auth; PII handling (support/CS data is PII-heavy → mandatory redaction).

## Findings

| Platform | Read REST API | Native signed webhook (push) | Surface verdict | Tier | Priority | Bar now? |
|---|---|---|---|---|---:|---|
| **Zendesk** | Yes — `/api/v2`, versioned, API token / OAuth scopes | **Yes** — HMAC-SHA256(`timestamp + body`), `x-zendesk-webhook-signature` + timestamp header | Evidence adapter (**webhook-first**) | T1 | **P1** | **Yes** |
| **ServiceNow** | Yes — Table API `/api/now/table`, versioned, OAuth/Basic | No — bespoke per-tenant Business-Rule outbound, no portable signing | Evidence adapter (poll-first) | T1 | P2 | API yes; defer build |
| **ChurnZero** | Yes — REST Bulk Read (ChurnScores, events, surveys), Basic | No — alerts to app/email/Slack/Teams only | Evidence adapter (poll-only) | T1 | P3 | API yes; defer |
| **Gainsight** | Yes — Bulk REST (Company health/renewal, Scorecards), Access Key/OAuth | No — Rules-Engine "Call External API", no managed signing | Evidence adapter (poll-only) | T1 | P3 | API yes; defer |

## Verdicts

- **All four are evidence adapters — none route to MCP.** Each is a records/events → Observation surface; no agent must act at inference time to *read* support pressure / customer health. MCP would only enter if someone wants to *create/mutate* tickets/incidents/CTAs (out of scope).
- **Zendesk — P1, catalog + queue for build (upgrade from P2).** The only one shipping the repo's preferred pattern: a first-class HMAC-SHA256 signed webhook with a timestamp/anti-replay header, directly reusable against `adapter/core/webhook_security.py` (the Linear/Sentry hex-HMAC + timestamp-window precedent). Highest decision-relevance (SLA breach + CSAT + ticket state). **Single gating dependency: the PII-redaction model must land before ticket bodies are ingested** (the catalog's named out-of-scope line for broad-customer-PII connectors).
- **ServiceNow — P2, newly catalogued, defer behind Zendesk.** Strong versioned read API and real ITSM evidence (incidents/changes/problems, change-governance), but **poll-only** for our purposes (no portable signed-webhook contract — every tenant's outbound is hand-rolled) and per-tenant customized. Scope a read-only role (Table API honors ACLs; over-scoped service accounts leak).
- **ChurnZero / Gainsight — P3, "CS health" theme, defer as a pair.** Both poll-only, both PII + commercially sensitive (renewal/churn risk is board-level). ChurnZero has the cleaner read API (explicit Bulk Read of ChurnScores); Gainsight has the richer evidence model but the most tenant-customized object schema (highest parse/maintenance risk). Pick up together once a real demand signal appears and redaction exists.

## Recommendation / next actions

1. **Zendesk → P1 candidate** (done in catalog §6.8). Build is a future governed cycle: `parse_ticket`/`parse_satisfaction` + `ZendeskConnector.verify()` reusing `verify_hmac_hex` over `timestamp + body` (Base64, not hex — confirm encoding at build time) — **after** the redaction model. Catalogued, not built this pass.
2. **ServiceNow → P2 candidate** (added to catalog §6.8). Poll connector; defer.
3. **ChurnZero + Gainsight → P3** (catalog notes refreshed). Defer as a CS-health pair.
4. **Cross-cutting blocker**: a customer-PII **redaction model** gates the support/CS build set — track as the prerequisite (the producer sensitive screen `FX-SEC-001` exists; confirm it covers ticket/CS free-text shapes before ingest).

## Sources (verified 2026-06-04)
- Zendesk: developer.zendesk.com — Ticketing API `/api/v2`, OAuth tokens, Webhooks "Verifying authenticity" (HMAC-SHA256 `x-zendesk-webhook-signature` + timestamp), Satisfaction Ratings, Ticket metric events, rate-limit best practices.
- ServiceNow: Table API (`/api/now/table`), inbound REST rate limiting, HMAC validation community guide (bespoke outbound), Scripted REST API webhooks.
- ChurnZero: app.churnzero.net/developers (REST + Bulk Read), Real-Time Alerts (app/email/Slack/Teams), REST API feature page.
- Gainsight: support.gainsight.com — API Documentation Overview, Bulk REST APIs, Company API, Generate REST API Key, Rules-Engine "Call External API" action.
