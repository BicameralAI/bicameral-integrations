# Sentry Connector — Canonical References

Single place tracking the canonical documentation links for the `sentry` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | observability/incident-evidence |
| Priority | P1 |
| Default trust tier | T1 |
| Integration role | runtime error/issue evidence |
| Readiness (lifecycle) | Beta (parse + `Sentry-Hook-Signature` HMAC verify, proven end-to-end through the `runtime/` harness against a reference sink; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://docs.sentry.io/api/ |
| Webhook/event | https://docs.sentry.io/organization/integrations/integration-platform/webhooks/issues/ |
| Auth | `Sentry-Hook-Signature` hex HMAC-SHA256 over the body, integration Client Secret (confirmed live 2026-06-13) |
| Changelog/notes | https://docs.sentry.io/ |

> **Doc-standard attestation (ledger #176, 2026-06-13):** this `references.md` (verified-contract section + provider-docs table + PII handling) + `auth.md` (signature scheme + deferred paths) + `config.json` (explicit `pii_posture` + `wire_gates` + `live_readiness`) assessed against the connector documentation standard — **EXCEEDS minimum**.

## Verified API/webhook contract (as built, 2026-06-05; signature re-verified live 2026-06-13)

- **Issue webhook event (parsed)**: `parse_issue` unwraps `{action, data.issue.{id, title, culprit, shortId, permalink, firstSeen, level, status}}`; falls back to treating the payload as a bare issue object when `data.issue` is absent. Excerpt is `title` falling back to `culprit`, `shortId`, then `id`.
- **Verification (built)**: `Sentry-Hook-Signature` = hex HMAC-SHA256 of the **raw received bytes** (not re-serialized); `verify()` calls `verify_hmac_hex` (fail-closed, constant-time). Re-verified against [docs.sentry.io integration-platform webhooks](https://docs.sentry.io/organization/integrations/integration-platform/webhooks/) on 2026-06-13: hex HMAC-SHA256 over the body with the integration **Client Secret** — MATCH (the connector verifies raw bytes, more robust than the doc's `JSON.stringify` example, which avoids re-serialization key-order drift). Dedup on `Request-ID` header then `issue.id`; no anti-replay timestamp window.
- **Auth (deferred)**: integration client secret injected by operator runtime; REST API issue fetch (active fallback) deferred. No live network this cycle.
- **Modes**: webhook only; no active/passive modes declared.
- **PII handling**: issue `title` (the exception message) + `culprit` (a code frame) are emitted via **redact-and-pass** — `adapter.core.redaction.redact` scrubs secret/PHI/PAN + email/phone (error messages routinely embed connection strings/emails/tokens; FX-SEC-001 backstops only secret/PHI/PAN). The opaque `shortId`/`id` floor is NOT redacted; the **full stack trace / event body is never read** (data minimization). No `author` field. Producer sensitive screen (`FX-SEC-001`) remains the fail-closed backstop for secret/PHI/PAN.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
