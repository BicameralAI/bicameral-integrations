# Research Brief

**Date**: 2026-06-04
**Analyst**: The Qor-logic Analyst
**Target**: Implement the four Phase-1 P0 candidate connectors scaffolded in the strategy cycle — **sarif**, **slack**, **notion**, **mcp_registry** — as provider-neutral parse surfaces.
**Scope**: Payload shapes for each + mapping onto `adapter.core` `Observation`/`normalize()`. Live network/auth/webhook-verification DEFERRED (parse-surface convention, FX-GH-001 precedent). Sources: provider docs (verified) + the now-canonical `docs/INTEGRATION_DOCS_INDEX.md` / `INTEGRATION_CANDIDATE_CATALOG.md`.

---

## Executive Summary

All four candidates (catalog §6, Phase-1 §8) are read-first evidence sources that fit the existing `Observation`→`normalize()` seam with zero contract change — same parse-surface shape as `connectors/github`. Trust tiers: **sarif T0** (static import), **notion T1**, **mcp_registry T1**, **slack T2** (the catalog's "notify-first" mode is a *write* concern deferred; the read/ingest evidence surface is what we build now, honoring "evidence before action"). The producer sensitive screen (`FX-SEC-001`) is the relevant guard — SARIF results and Slack messages can carry secrets/PII. No blocking gaps → `/qor-plan` at L2.

## Findings

### F1 — SARIF 2.1.0 (T0, static import; security evidence)
Shape (OASIS spec): `{version, runs:[{tool:{driver:{name}}, results:[{ruleId, level, message:{text}, locations:[{physicalLocation:{artifactLocation:{uri}, region:{startLine}}}]}]}]}`. Map **one Observation per result**: `source_id="sarif"`, `ref=f"{ruleId}@{uri}:{startLine}"`, `kind="finding"`, `excerpt=message.text`, `title=ruleId`, `metadata={tool, level, uri, startLine}`. `observations(report)` returns all results across runs. File ingest only (no auth).

### F2 — Slack message (T2; communication/decision capture)
Shape (Events API / conversations.history): a message `{type:"message", text, user, channel, ts}` (Events API wraps it as `{event:{...}}`). Map: `source_id="slack"`, `ref=f"{channel}:{ts}"`, `kind="message"`, `excerpt=text`, `author=user`, `timestamp=ts` (Slack `ts` is an epoch string). `parse_message` accepts either the bare message or an `event_callback` envelope (`payload.get("event") or payload`). Notify/write deferred (T3+); this is read/ingest.

### F3 — Notion page (T1; docs/knowledge)
Shape (verified developers.notion.com/reference/page): `{object:"page", id, url, created_time, last_edited_time, created_by:{id}, properties:{<name>:{type:"title", title:[{plain_text}]}}}`. Title = the property whose `type=="title"`, joining its `title[].plain_text`. Map: `source_id="notion"`, `ref=id`, `url`, `kind="page"`, `title=<title>`, `excerpt=title` (page object carries no body — blocks are a separate fetch, deferred), `author=created_by.id`, `timestamp=last_edited_time`.

### F4 — MCP Registry server.json (T1; mcp ecosystem)
Shape (verified modelcontextprotocol/registry server.json): `{name, description, title, version, repository:{url, source, id}, packages, remotes, websiteUrl}`. Map: `source_id="mcp_registry"`, `ref=name`, `url=repository.url or websiteUrl`, `kind="mcp_server"`, `title=title or name`, `excerpt=description or title or name`, `metadata={version, repository_source}`. Read-only scoring/allowlist (T1).

### F5 — Contract fit + safety
All four: read-only parse surfaces emitting `Observation` → `pipeline.normalize()`; no canonical writes (ADR-0008 evidence-adapter boundary). Non-empty-excerpt fallback chains required (normalize rejects blank). Fixtures synthetic/PII-safe (`example.com`, no Luhn PAN, no secret-shaped tokens) so `FX-SEC-001` + TruffleHog stay green. Trust tier + provider docs already recorded in each connector's `references.md`.

## Blueprint Alignment

| Claim | Finding | Status |
|---|---|---|
| Catalog Phase-1 P0 = GitHub/Linear/Jira/Slack/Notion/SARIF/MCP-Registry | sarif/slack/notion/mcp_registry are the unbuilt P0 set | MATCH |
| Evidence adapters, not state authorities (ADR-0008) | all read-only → Observation; no writes | MATCH |
| Trust-tier model (T0–T5) | sarif T0, notion/mcp T1, slack T2 (read surface) | MATCH |
| Observation/AdapterEmission contract unchanged | four shapes fit existing fields | MATCH |

No DRIFT.

## Recommendations

1. **[P1] `/qor-plan` at L2.** One plan, four connectors: `parse_*(payload)->Observation` (sarif returns a list) + `<Provider>Connector.observations` + fixture + end-to-end `normalize()` conformance test each; flip scaffold READMEs Candidate→Prototype.
2. **[P1] Defer live paths** (HTTP/Events-API/file-watch/registry-fetch + auth + Slack webhook signing) — record in each `auth.md`; parse surface only.
3. **[P2] Fixtures PII-safe**; SARIF fixture uses a benign finding (no real secret in the snippet).

## Updated Knowledge

SHADOW_GENOME **SG-2026-06-04-F**: the four Phase-1 candidate shapes (SARIF result, Slack message/event-callback, Notion title-property page, MCP server.json) all reduce to the same `Observation` parse surface; Slack's "notify-first" catalog mode is a deferred T3 write concern, not the read/ingest evidence surface built here (evidence-before-action, ADR-0008).

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
