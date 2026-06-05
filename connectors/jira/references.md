# Jira Cloud Connector — Canonical References

Single place tracking the canonical documentation links for the `jira` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | project-management |
| Priority | P0 |
| Default trust tier | T1/T3 |
| Integration role | evidence + event |
| Readiness (lifecycle) | Beta (proven end-to-end through the `runtime/` harness against a reference sink; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/ |
| Webhook/event | https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-webhooks/ |
| Auth | https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/ |
| Changelog/notes | https://developer.atlassian.com/cloud/jira/platform/changelog/ |

## Verified API/webhook contract (as built, 2026-06-05)

- **Issue webhook event (parsed)**: `parse_issue` reads `{webhookEvent, issue_event_type_name, issue.{key, id, self, fields.{summary, updated, created, status.name, issuetype.name, project.key}}, user.displayName, timestamp}`; excerpt is `fields.summary` (never `fields.description` — that field is an ADF object, not a string).
- **Verification (built)**: `X-Hub-Signature: sha256=<hex HMAC-SHA256(secret, raw_body)>` (WebSub); `verify()` strips `"sha256="` prefix and calls `verify_hmac_hex` (fail-closed, constant-time). Dedup on `X-Atlassian-Webhook-Identifier` then `issue.id`; no anti-replay timestamp window (Jira documents none).
- **Auth (deferred)**: `webhook_secret` (verify) + `api_email`/`api_token` (REST fetch, HTTP Basic) or OAuth 2.0 3LO; Connect-JWT/Forge/Automation paths not implemented. No live network this cycle.
- **Modes**: webhook (primary) + active (REST fallback); both share `parse_issue`.
- **PII handling**: `fields.summary` emitted (issue title only); ADF `description` body deliberately excluded. Producer sensitive screen (`FX-SEC-001`) is the guard.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
