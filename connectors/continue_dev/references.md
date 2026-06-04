# Continue Connector — Canonical References

Single place tracking the canonical documentation links for the `continue` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | source-control / developer-AI tooling |
| Priority | P1 |
| Default trust tier | T0 |
| Integration role | evidence + provenance (developer-AI interactions) |
| Readiness (lifecycle) | Prototype |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://docs.continue.dev/reference (config `data` block + `schema`) |
| Development data | https://docs.continue.dev/customize/deep-dives/development-data |
| Event schemas | https://github.com/continuedev/continue/tree/main/packages/config-yaml/src/schemas/data |
| Webhook/event | No public read API/webhook; local JSONL or user-hosted HTTP sink |
| Auth | None for local file ingest; Bearer `apiKey` for HTTP sink |
| Changelog/notes | https://github.com/continuedev/continue |

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
