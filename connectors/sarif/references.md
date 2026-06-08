# SARIF 2.1.0 Connector — Canonical References

Single place tracking the canonical documentation links for the `sarif` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | security/compliance-evidence |
| Priority | P0 |
| Default trust tier | T0 |
| Integration role | static-import evidence |
| Readiness (lifecycle) | Beta (proven end-to-end through the `runtime/` harness against a reference sink; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html |
| Webhook/event | File import only |
| Auth | Not applicable (file ingest) |
| Changelog/notes | https://github.com/oasis-tcs/sarif-spec |

## Verified API/webhook contract (as built, 2026-06-05)

- **SARIF 2.1.0 report (parsed)**: `parse_sarif` flattens `runs[].results[]` — one Observation per result; `parse_result` reads `{ruleId, level (enum none|note|warning|error), message.text, locations[0].physicalLocation.{artifactLocation.uri, region.startLine}}`; ref is `"{ruleId}@{uri}:{startLine}"`; tool name from `run.tool.driver.name`. (Verified 2026-06-08 against the OASIS SARIF 2.1.0 schema — all paths + the `level` enum confirmed.)
- **Verification**: no verify — file import (T0); no network delivery, no signature.
- **Auth (deferred)**: none applicable (file ingest); live file-watch/CI-collection path deferred.
- **Modes**: passive only (file import); no webhooks.
- **PII handling**: static-analysis finding messages, file URIs, and rule IDs emitted; no user PII in the SARIF schema by design.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
