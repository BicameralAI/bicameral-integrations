# Linear Connector — Canonical References

Single place tracking the canonical documentation links for the `linear` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | project-management |
| Priority | P0 |
| Default trust tier | T1/T3 |
| Integration role | evidence + event |
| Readiness (lifecycle) | Beta (parse + webhook verify, proven end-to-end through the `runtime/` harness against a reference sink; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://linear.app/docs/api-and-webhooks |
| Webhook/event | https://linear.app/developers/webhooks |
| Auth | https://linear.app/developers/oauth |
| Changelog/notes | https://linear.app/changelog |

## Verified API/webhook contract (as built, 2026-06-05)

- **Webhook event envelope (parsed)**: `parse_event` reads `{action, type, actor.name, createdAt, organizationId, webhookId, webhookTimestamp, data.{identifier, id, title, description, url}}`; title combines `identifier` + `data.title`; excerpt is `data.description` falling back to title then identifier.
- **Verification (built)**: `Linear-Signature` header = hex HMAC-SHA256 of the raw body using the webhook signing secret; `verify()` calls `verify_hmac_hex` first, then enforces a **60-second anti-replay window** on `webhookTimestamp` (UNIX ms). Dedup on `webhookId`. Fail-closed.
- **Auth (deferred)**: personal API key in `Authorization` header for GraphQL active fetch (`https://api.linear.app/graphql`); signing secret injected by operator runtime. No live network this cycle.
- **Modes**: webhook (primary — envelope carries change context) + active (GraphQL fallback); both share `parse_event`.
- **PII handling**: `data.description` and `actor.name` emitted; `organizationId` in metadata. Producer sensitive screen (`FX-SEC-001`) is the guard.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
