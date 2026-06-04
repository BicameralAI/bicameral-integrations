# Research Brief

**Date**: 2026-06-04
**Analyst**: The Qor-logic Analyst
**Target**: Implement the **Jira Cloud** connector (P0 foundation) — issue-webhook parse surface **with `verify()` wired from the start** (parity with the hardened connectors).
**Scope**: `parse_issue(event) -> Observation` + `JiraConnector.verify()/normalize_event()`; live HTTP receipt + REST fetch + secret resolution deferred. Sources: developer.atlassian.com (cited); verified/uncertain tagged.

---

## Executive Summary

Jira Cloud classic (admin-registered) webhooks **support HMAC verification** — with a configured `secret`, delivery is signed `X-Hub-Signature: sha256=<hex-HMAC-SHA256(secret, raw_body)>` (WebSub). So Jira ships **with `verify()` at parity** with Linear/Sentry — the only delta is **stripping the `sha256=` prefix** before reusing `verify_hmac_hex` (which expects bare hex). Issue payload maps cleanly: title = `fields.summary` (plain str); **`fields.description` is an ADF object, NOT a string** → excerpt uses `summary` only (never ADF), with a `jira-issue` terminal floor (SG-2026-06-04-G). No documented anti-replay window → best-effort dedup on `X-Atlassian-Webhook-Identifier` (consistent across retries), fallback `issue.id`. Connect-JWT / Forge / Automation auth are a separate deferred path. P0, WEBHOOK (+ ACTIVE REST fallback), trust tier T1.

## Findings

### F1 — Issue webhook payload (verified)
`{timestamp (epoch ms), webhookEvent ("jira:issue_created"|…), issue_event_type_name, user{displayName, accountId, …}, issue{id, key, self, fields{summary (str), description (ADF dict), status.name, issuetype.name, project.key, priority, assignee, reporter, created, updated}}, changelog?, comment?}`. The webhook `user` has **no `emailAddress`** (less PII than REST). [verified]

### F2 — ADF description (verified — the schema trap)
`fields.description` (and comment `body`) is **Atlassian Document Format** (`{type:"doc", version, content:[…]}`), not text. The connector must **not** read/stringify ADF into the excerpt (meaningless + could smuggle PII past intent). Excerpt = `fields.summary` → `key` → `id` → `"jira-issue"` floor.

### F3 — Verification (verified — the crux, resolved YES)
Classic webhook with a `secret` → `X-Hub-Signature: sha256=<hex-HMAC-SHA256(secret, raw body)>`. `verify()` = strip a leading `sha256=` (case-insensitive) then `verify_hmac_hex(header_sig=<bare hex>, body=raw, secret=…)`, fail-closed (empty secret / missing header / mismatch → False). HMAC over the **exact raw bytes** (the #1 community failure is re-serializing first). **No documented anti-replay window** → no timestamp gate; replay mitigation is dedup-TTL + TLS (operator residual risk, documented). Connect apps use HS256/RS256 JWT (`qsh`); Forge/Automation use platform auth — all **deferred** (document in `auth.md`).

### F4 — Dedup + REST fallback (verified)
Dedup id: `X-Atlassian-Webhook-Identifier` header (stable across retries), fallback `issue.id`; best-effort (process when absent, never drop). REST fallback `GET /rest/api/3/issue/{idOrKey}` returns the same `fields` shape (description still ADF); auth Basic (email+API token)/OAuth — deferred. `issue.self` is the REST URL; the human browse URL is more reviewer-useful but only best-effort reconstructable → `url = issue.self` (or browse if cleanly derivable).

### F5 — Contract fit + safety
Read-only parse → Observation → normalize() (zero contract change). Defend every field (SG-2026-06-04-I): `issue`/`fields`/`status`/`project`/`issuetype`/`user` may be absent/null/wrong-typed; reuse the Sentry `_text()` discipline. Transcripts/issue bodies can carry secrets/PII → `FX-SEC-001` is the guard.

## Blueprint Alignment

| Claim | Finding | Status |
|---|---|---|
| Jira P0 foundation (catalog §6.2/§8) | webhook + REST, HMAC verify available | MATCH |
| verify() parity (operator: "wired from the start") | `X-Hub-Signature` HMAC (strip `sha256=`) | MATCH |
| Don't share one verifier blindly (SG-A) | Jira = hex HMAC w/ `sha256=` prefix (distinct from PagerDuty multi-sig) | MATCH |
| Terminal floor (SG-G) + type defense (SG-I) | `jira-issue` floor; ADF never read; `_text` guards | MATCH |

No DRIFT.

## Recommendations
1. **[P0] `/qor-plan` at L3** (verify path) — `parse_issue` + `_text` + `JiraConnector.verify()` (strip `sha256=` → `verify_hmac_hex`) / `normalize_event()` (self-guard → JSON guard → best-effort dedup on `X-Atlassian-Webhook-Identifier`|`issue.id` → parse); synthetic fixture + signed companion; behavioral + fail-open tests.
2. **[P1] Defer** live HTTP receipt, REST fetch, secret/keyring resolution, and the Connect-JWT/Forge/Automation auth paths — record in `auth.md`.
3. **[P2]** Excerpt = `summary` only (never ADF); document the no-replay-window limitation honestly.

## Updated Knowledge
SHADOW_GENOME (proposed) **SG-2026-06-04-M**: Jira Cloud classic webhooks DO sign (`X-Hub-Signature: sha256=` hex HMAC over raw body, WebSub) — but the `sha256=` prefix must be stripped before a bare-hex verifier; and `fields.description` is ADF (a dict), so the excerpt must use `summary`, never the description. Reinforces SG-A (per-provider signature divergence) + SG-I (ADF dict is not text).

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
