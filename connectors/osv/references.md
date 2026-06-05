# OSV Connector — Canonical References

Single place tracking the canonical documentation links for the `osv` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | security/compliance-evidence |
| Priority | P0 |
| Default trust tier | T1 (no-auth) |
| Integration role | vulnerability evidence (supply-chain aggregator) |
| Readiness (lifecycle) | Beta (proven end-to-end through the `runtime/` harness against a reference sink; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://google.github.io/osv.dev/api/ |
| Schema | https://ossf.github.io/osv-schema/ |
| Webhook/event | No webhook; read-only query API |
| Auth | None (free, unauthenticated) |
| Changelog/notes | https://github.com/google/osv.dev |

## Verified API/webhook contract (as built, 2026-06-05)

- **Vulnerability record (parsed)**: `parse_vuln` reads the OSV schema — `{id, summary, details, modified, severity[{type, score}], references[{url}], affected[{package.{name}}], aliases[]}`; excerpt is `summary` falling back to `details` then `id`; metadata carries joined `severity`, `packages`, and `aliases` strings.
- **Verification**: no verify — read-only query API; no webhook delivery, no signature.
- **Auth (deferred)**: none (OSV.dev is free and unauthenticated); live query client (`POST /v1/query`, `/v1/querybatch`, `GET /v1/vulns/{id}`) deferred. No live network this cycle.
- **Modes**: active only (query API); no webhooks.
- **PII handling**: vulnerability metadata only (CVE ids, package names, severity scores); no user PII in the OSV schema.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
