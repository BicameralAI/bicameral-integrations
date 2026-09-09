# Jira Connector

Read-only evidence connector: it verifies and parses Jira Cloud issue webhooks
into neutral `Observation`s. **Component status: Beta** (ADR-0012; catalog
project-management, priority P0, default trust tier T1/T3). A Phase-1 foundation
connector from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Webhook** — a Jira Cloud issue webhook (`jira:issue_created` / `_updated` /
  `_deleted`) maps to one neutral `Observation` (`parse_issue`), with signature
  verification wired (`verify()`/`normalize_event()`). Read-only evidence; no
  canonical writes (ADR-0008). The live HTTP receiver remains deferred.
- **Active** — the connector has the Jira issue parsing/capability surface for
  REST `GET /rest/api/3/issue/{key}`, but the live REST fetch is deferred and is
  not an alpha-admitted ingest path.

`X-Hub-Signature` (`sha256=` hex HMAC-SHA256 over the raw body, fail-closed)
verification and best-effort dedup are implemented in `verify()` /
`normalize_event()`. The live boundary — HTTP webhook receipt, the REST poll
fetch, secret/keyring resolution, and the Connect-JWT / Forge / Automation auth
paths — stays in the operator runtime (see [`auth.md`](auth.md)).

## Readiness: component-ready, alpha-excluded

The Jira connector is **Beta at the component level**. Its signed-webhook →
`runtime.deliver_webhook` → reference-sink path is covered by component tests,
and the provider-specific parse, signature-verification, dedup, and redaction
surfaces are implemented.

That does **not** mean Jira is Live, alpha-admitted, terminally proven, or human
accepted. The canonical alpha ingest manifest currently excludes Jira because
the live HTTP receiver and REST fetch remain deferred. `GatewaySink` being
available means gateway delivery is implementable; it is not evidence that Jira
has completed a real provider-to-Bot journey.

For Jira to advance beyond component readiness, the operator path must provide a
real receiver and secret, record a real signed Jira delivery, deliver the
resulting evidence through `GatewaySink` to Bot, capture the resulting receipts,
and satisfy the applicable terminal and human-acceptance gates.

Descriptor terminology is intentionally narrower:

- `status` / `live-ready` describe connector implementation and packaging
  maturity only;
- `available` controls whether the connector can be presented/configured;
- alpha admission and conformance are owned by `ingest/alpha-ingest-manifest.json`;
- terminal proof and human acceptance are separate downstream gates.

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
