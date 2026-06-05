# PagerDuty Connector — Canonical References

Single place tracking the canonical documentation links for the `pagerduty` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | observability/incident-evidence |
| Priority | P1 |
| Default trust tier | T1 |
| Integration role | incident/on-call evidence |
| Readiness (lifecycle) | Beta (parse + multi-signature `v1=` membership verify, proven end-to-end through the `runtime/` harness against a reference sink; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://developer.pagerduty.com/api-reference/ |
| Webhook/event | https://support.pagerduty.com/main/docs/webhooks |
| Auth | `X-PagerDuty-Signature` HMAC-SHA256 (multiple comma-separated rotating signatures) |
| Changelog/notes | https://developer.pagerduty.com/changelog/ |

## Verified API/webhook contract (as built, 2026-06-05)

- **V3 incident webhook envelope (parsed)**: `parse_event` unwraps `{event.{event_type, occurred_at, id, data.{id, title, summary, html_url, created_at, status, urgency}}}`; both the outer `event` dict and the nested `data` dict are isinstance-guarded; excerpt is `data.title`/`data.summary` falling back to `data.id`.
- **Verification (built)**: `X-PagerDuty-Signature` is a **comma-separated `v1=<hex>,v1=<hex>` set** (zero-downtime key rotation); `verify()` calls `verify_hmac_hex_multi` — accept if ANY `v1=` candidate HMAC-SHA256 matches the raw body (fail-closed, constant-time). Dedup on `event.id`; no anti-replay timestamp window.
- **Auth (deferred)**: webhook signing secret injected by operator runtime; REST API incident fetch (active fallback) deferred. No live network this cycle.
- **Modes**: webhook only; no active/passive modes declared.
- **PII handling**: incident `title`/`summary` and `html_url` emitted; `status` and `urgency` in metadata. Producer sensitive screen (`FX-SEC-001`) is the guard.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
