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
| Readiness (lifecycle) | Beta (proven end-to-end through the `runtime/` harness against a reference sink; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://docs.continue.dev/reference (config `data` block + `schema`) |
| Development data | https://docs.continue.dev/customize/deep-dives/development-data |
| Event schemas | https://github.com/continuedev/continue/tree/main/packages/config-yaml/src/schemas/data |
| Webhook/event | No public read API/webhook; local JSONL or user-hosted HTTP sink |
| Auth | None for local file ingest; Bearer `apiKey` for HTTP sink |
| Changelog/notes | https://github.com/continuedev/continue |

## Verified API/webhook contract (as built, 2026-06-05)

- **Dev-data event (parsed, verified 2026-06-08 docs.continue.dev)**: `parse_event` reads `{eventName (legacy `name` fallback), timestamp/ts, prompt, completion, content, message, userId, schema, modelTitle/modelName/model}`; the base schema field is **`eventName`** and there is **no event-id field** (ref floors to `eventName:timestamp`); excerpt is the first non-empty text field among `prompt`, `completion`, `content`, `message`, falling back to `"continue {eventName}"`. The schema (`0.1.0`/`0.2.0`) is documented to churn; all field access is str-coerced.
- **Verification**: no verify — passive file import; no network delivery, no signature.
- **Auth (deferred)**: none for local file ingest (T0); HTTP-sink path uses Bearer `apiKey` in `config.yaml` — deferred. No live network this cycle.
- **Modes**: passive only; no webhooks (provider id `"continue"`; package `continue_dev`).
- **PII handling**: prompts and completions may contain code and personal context; `level: noCode` strips text fields at source (operator-set). Producer sensitive screen (`FX-SEC-001`) is the in-pipeline guard.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
