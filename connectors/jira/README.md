# Jira Connector

Read-only evidence connector: it verifies and parses Jira Cloud issue webhooks
into neutral `Observation`s. **Status: Beta** (ADR-0012; catalog
project-management, priority P0, default trust tier T1/T3). A Phase-1 foundation
connector from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Webhook** — a Jira Cloud issue webhook (`jira:issue_created` / `_updated` /
  `_deleted`) maps to one neutral `Observation` (`parse_issue`), with signature
  verification wired (`verify()`/`normalize_event()`). Read-only evidence; no
  canonical writes (ADR-0008).
- **Active** — REST `GET /rest/api/3/issue/{key}` returns the same `fields`
  shape (live REST poll fallback).

`X-Hub-Signature` (`sha256=` hex HMAC-SHA256 over the raw body, fail-closed)
verification and best-effort dedup are implemented in `verify()` /
`normalize_event()`. The live boundary — HTTP webhook receipt, the REST poll
fetch, secret/keyring resolution, and the Connect-JWT / Forge / Automation auth
paths — stays in the operator runtime (see [`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its signed-webhook → `runtime.deliver_webhook` → reference
sink path is proven end-to-end by `runtime/tests/test_runtime.py`, with **zero
cross-repo dependency**. Live (gateway emission) is now operator-actionable — `GatewaySink` is real (bot #109 landed, PR #131); an operator configures it against a real gateway to go Live.

## Surface

- `parse_issue(event)` — Jira issue event → `Observation`. `fields.summary` →
  excerpt (with `key`/`id` then a `jira-issue` terminal fallback); **never the
  ADF `fields.description` object**; `key` → ref; `issue.self` → ref url;
  `user.displayName` → author; `updated`/`created`/`timestamp` → timestamp;
  `webhookEvent`/`status`/`issuetype`/`project` → metadata. Defends ADF/absent/
  wrong-typed throughout (SG-2026-06-04-I).
- `JiraConnector` — identity + capabilities (`WEBHOOK`, `ACTIVE`); `verify()`
  checks `X-Hub-Signature` (`sha256=` hex HMAC-SHA256 over the raw body,
  fail-closed); `normalize_event()` self-guards + best-effort dedup
  (`X-Atlassian-Webhook-Identifier` → `issue.id`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
