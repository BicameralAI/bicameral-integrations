# Research Brief

**Date**: 2026-06-04
**Analyst**: The Qor-logic Analyst
**Target**: Evaluate **Devin / Devin Desktop** (Cognition) as a candidate connector (BACKLOG B7) — value-add assessment, not a build.
**Scope**: §4 criteria + the surface-selection interactivity test (SG-2026-06-04-K). Sources: official docs (docs.devin.ai), cited; tagged verified/uncertain.

---

## Executive Summary

Devin (the Windsurf/Codeium successor — those docs now redirect to docs.devin.ai) ships an **official, versioned (v3) REST API** with read-only GET endpoints for sessions and messages. It **meets the bar via the API path**; the Desktop/Local path does **not** (no documented on-disk transcript artifact — unlike Claude Code's `~/.claude/**/*.jsonl`). The Bicameral-relevant surface is **read-only session evidence → a direct API evidence adapter (this repo, P1/T1)**; launching/steering Devin (`POST` sessions/messages) is agent-action and belongs in `bicameral-mcp` (T3/T5), out of scope here. Recommend **P1, ACTIVE (poll — no webhooks), T1**; build deferred behind the Claude Code P0. **No build this cycle** (B7 = research; closes with a build recommendation).

## Findings

### F1 — Devin API (verified)
Official REST API, versioned (`v3` current; `v1/v2` deprecating with a migration policy). Read-only GETs: list sessions (`GET /v3/organizations/{org}/sessions`), get session, **session messages** (`.../messages`, cursor pagination), insights. Auth: bearer service-user credential (`cog_`), RBAC (`ViewOrgSessions`-type read scope). **No webhooks** — status monitoring is poll-only. [verified: docs.devin.ai/api-reference]

### F2 — Session object as evidence (verified)
`session_id`, `url`, `status`/`status_detail`, `title`, `created_at`/`updated_at`, `tags`, `acus_consumed`, **`pull_requests[]`** (`{pr_url, pr_state}` — the high-value intent→code provenance link), `structured_output`, `category`, `parent_session_id`/`child_session_ids`. Messages: `{event_id, source: devin|user, message, created_at}`. A clean "agent did X toward goal Y, producing PR Z" provenance chain.

### F3 — Devin Desktop / Local (verified docs silent → NO file artifact)
Devin Desktop (rebranded Windsurf IDE) + Devin Local (local agent harness) run sessions locally but **session state is cloud/API-backed** and appears in the Agent Command Center; **no documented local session-log/transcript file format and no export**. Relying on an undocumented local cache would be brittle scraping → fails the bar. So Devin is an **API connector, not a file connector** (the opposite of Claude Code).

### F4 — Governance + interactivity test
Read-only ingestion: yes (GET sessions/messages, read-scoped service user). Data classes: prompts/messages (primary, sensitive), code (PR-side, GitHub), secrets (`secret_ids` on create — must not round-trip on read; message text could leak → redaction via `FX-SEC-001`), PII (`requesting_user_email`, `user_id`). **Interactivity test (SG-K)**: ingesting session evidence = **evidence adapter (this repo, T1)**; `POST` to launch/steer Devin = agent action = **bicameral-mcp (T3/T5)**, out of scope. Clean split, mirrors Claude Code.

## Recommendation

- **Priority: P1.** High-value agentic-provenance evidence with a first-class read API; natural sibling to the Claude Code (P0) connector.
- **Mode: ACTIVE (poll)** — no webhooks; periodic `GET sessions` (filter by tag/recency) → `GET {id}` + `GET {id}/messages`. File mode not viable.
- **Trust tier: T1** (authoritative first-party API, RBAC read-only service user; T0 reserved for local on-disk, which Devin lacks).
- **parse → Observation sketch (for the future build):** `session → Observation(source_id="devin", ref=session_id, url=session.url, excerpt=title or prompt with id floor, kind="session", metadata={status, pull_requests, structured_output, acus_consumed, parent/child})`; `message → Observation(ref=event_id, excerpt=message text with floor, kind="message", metadata={source, created_at})`. Defend wrong-typed/absent (SG-I); terminal-literal excerpt floor (SG-G).
- **Biggest risk:** v3 schema churn (freshly shipped, v1/v2 deprecating) — pin to v3 + snapshot the schema; and message bodies can carry secrets/PII → redaction mandatory. (No webhooks is a minor inconvenience, not a blocker.)
- **No build this cycle.** Queue a governed Devin build behind Claude Code.

## Updated Knowledge

Reinforces SG-2026-06-04-K: Devin cleanly splits into a read-only evidence surface (sessions API → adapter here) vs an agent-action surface (launch/steer → bicameral-mcp). Contrast with Claude Code: same "agentic coder" class, **opposite ingestion surface** — Claude Code = local file (T0), Devin = cloud API (T1).

---

_Research complete (B7). Findings are advisory — implementation decisions remain with the Governor._
