# Research Brief

**Date**: 2026-06-04
**Analyst**: The Qor-logic Analyst
**Target**: Phase-2 connector tranche (security & operational evidence) — build the genuinely-new evidence classes as provider-neutral parse surfaces.
**Scope**: `parse_*(payload) -> Observation -> normalize()`, read-only (ADR-0008), live network/auth/webhook-verification DEFERRED to `auth.md`. Apply the §4 interactivity test (all are evidence adapters, not MCP). Sources: official docs (cited in the cycle research transcript), grounded + tagged verified/uncertain.

---

## Executive Summary

Of the six Phase-2 candidates (catalog §8 + the value-add P0 lead), **three are genuinely new evidence classes worth dedicated connectors — OSV.dev (P0, vulnerability), Sentry (P1, runtime error), PagerDuty (P1, incident)** — and three are not: **Semgrep ⊂ SARIF** and **GitHub Code Scanning ⊂ SARIF** (ingest via the existing `sarif` connector / its API is a lossy projection), and **Datadog** is deferred (dual-key auth → T2, noisy payloads needing alert-type filtering). All three build targets reduce to the existing seam with zero contract change; all pass the interactivity test as evidence adapters. Build order favors low-auth/high-value: **OSV.dev first** (no auth), then the two webhook connectors (reuse the Linear/Fathom `verify()`/dedup pattern, deferred).

## Findings

### F1 — OSV.dev (P0; vulnerability evidence; ACTIVE/T1, no-auth)
Read API `POST /v1/query`, `/v1/querybatch`, `GET /v1/vulns/{id}` [verified]; **free, unauthenticated, no current rate limit** (32 MiB HTTP/1.1 cap) [verified]. OSV schema: only `id` + `modified` are required; `summary`/`details`/`affected[]`/`severity[]`/`references[]`/`aliases` are optional [verified]. **Map** `parse_vuln(v)`: `source_id="osv"`, `ref=v["id"]`, `url=first references[].url or ""`, `kind="vulnerability"`, `excerpt=summary or details or id` (the required `id` is the terminal floor — SG-2026-06-04-G), `title=summary or id`, `timestamp=modified`, `metadata={severity, affected_packages, aliases}`. `mode=ACTIVE` (read-API convention). Biggest risk: optional-everything schema + `affected[]`/`severity[]` are arrays of objects → defend on absence/wrong-type (SG-2026-06-04-I). Trust tier T1 (no-credential special case noted in `auth.md`).

### F2 — Sentry (P1; runtime-error/issue evidence; WEBHOOK/T1)
Issue webhook + REST [verified]. Webhook payload: `action`, `data.issue.{id, title, culprit, level, permalink, shortId, firstSeen, status}`, header `Sentry-Hook-Resource: issue` [verified]. **Map** `parse_issue(event)`: unwrap `data.issue`; `source_id="sentry"`, `ref=issue["id"]`, `url=permalink`, `kind="issue"`, `excerpt=title or culprit or shortId or id` (terminal floor), `author=""`, `timestamp=firstSeen`, `metadata={action, level, status, culprit, shortId}`, `mode=WEBHOOK`. Live receipt + signature verify (`Sentry-Hook-Signature` HMAC-SHA256 — exact header/algo `[uncertain]`, confirm before live) DEFERRED to `auth.md`. Risk: `level` taxonomy (`fatal|error|warning|info`) → metadata, not lossy map.

### F3 — PagerDuty (P1; incident/on-call evidence; WEBHOOK/T1)
v3 webhook + REST [verified]. **Nested envelope**: `event.{id, event_type, resource_type, occurred_at, agent, data}`; for an incident `event.data.{id, type, html_url, number, status, title, urgency, service, created_at}` [verified]. **Map** `parse_event(envelope)`: `ev = envelope["event"]`, `d = ev["data"]`; `source_id="pagerduty"`, `ref=d["id"]`, `url=d.html_url`, `kind="incident"`, `excerpt=d.title or d.summary or d.id` (terminal floor `"pagerduty-incident"`), `timestamp=d.created_at or ev.occurred_at`, `metadata={event_type: ev.event_type, status, urgency, service}`, `mode=WEBHOOK`. Live verify: `X-PagerDuty-Signature` HMAC-SHA256 with **multiple comma-separated rotating signatures** (membership check, not equality) [verified] — DEFERRED to `auth.md`. Risk: guard BOTH envelope levels for wrong-type (SG-2026-06-04-I).

### F4 — Do NOT build (overlap/deferred)
- **Semgrep (P3)** — `semgrep --sarif` is standard SARIF 2.1.0 → ingest via the existing `sarif` connector (`tool.driver.name == "semgrep"`). Document, don't duplicate.
- **GitHub Code Scanning API (P2)** — a lossy projection of the SARIF result the `sarif` connector already parses; only net-new field is alert `state`/`dismissed_reason`. Defer; if built later, reuse the `sarif` Observation shape, not a parallel parser.
- **Datadog (P2)** — dual-key (DD-API-KEY + DD-APPLICATION-KEY → T2) + noisy mixed-source events needing `alert_type` filtering. Defer behind a normalization filter.

### F5 — Contract fit + interactivity
All three build targets: read-only parse surfaces → `Observation` → `pipeline.normalize()`; no canonical writes. Excerpt terminal-literal floor (SG-2026-06-04-G) + wrong-type defense (SG-2026-06-04-I) required. Interactivity test: all three are **evidence adapters** (ingest findings/issues/incidents), not agent-action surfaces → API/webhook, not MCP. OSV ACTIVE (read API); Sentry/PagerDuty WEBHOOK (push) — and webhook push can only come direct, never via MCP (SG-2026-06-04-K).

## Blueprint Alignment

| Claim | Finding | Status |
|---|---|---|
| Build the new evidence classes, not SARIF-redundant ones | OSV/Sentry/PagerDuty new; Semgrep/CodeQL-API ⊂ SARIF | MATCH |
| Evidence adapters, not authorities (ADR-0008) | all read-only → Observation | MATCH |
| Interactivity test (SG-K) | all evidence adapters; none MCP | MATCH |
| Trust tiers | OSV T1 (no-auth), Sentry/PagerDuty T1/WEBHOOK | MATCH |
| Excerpt terminal floor (SG-G) + type defense (SG-I) | `id`/`title`-with-literal floors; defensive `.get` | MATCH |

No DRIFT.

## Recommendations

1. **[P0] `/qor-plan` at L2** — one plan, three connectors: OSV `parse_vuln` (ACTIVE), Sentry `parse_issue` (WEBHOOK), PagerDuty `parse_event` (WEBHOOK). Each: parse surface + `<Provider>Connector` + synthetic fixture + behavioral end-to-end `normalize()` test; READMEs at Prototype; FEATURE_INDEX rows.
2. **[P1] Defer live paths** — OSV query client; Sentry/PagerDuty webhook receipt + HMAC verify (Sentry single-sig; PagerDuty multi-sig rotation) + dedup — record in each `auth.md` (mirror Linear/Fathom).
3. **[P2] Do not build** Semgrep/CodeQL-API/Datadog this cycle — document the SARIF path for the first two; defer Datadog.

## Updated Knowledge

Confirms SG-2026-06-04-J (aggregator: OSV subsumes per-ecosystem feeds) and SG-2026-06-04-K (evidence-adapter vs MCP). PagerDuty's multi-signature rotation is a new wrinkle to design the deferred `verify()` around (membership, not equality).

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
