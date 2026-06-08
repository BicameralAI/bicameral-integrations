# Granola Connector — Canonical References

Single place tracking the canonical documentation links for the `granola` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | meetings/transcripts |
| Priority | P3 |
| Default trust tier | T1/T5 |
| Integration role | evidence |
| Readiness (lifecycle) | Beta (proven end-to-end through the `runtime/` harness against a reference sink; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://developers.granola.ai/ |
| Webhook/event | Validate webhook availability before implementation |
| Auth | API-key (env-injected); validate auth model |
| Changelog/notes | Candidate |

## Verified API contract (doc-confirmed 2026-06-08, docs.granola.ai)

- **Note payload (parsed)**: `parse_transcript` reads `{id (not_ prefix), title, transcript[] of {speaker, text}, attendees[] of {name, email}, created_at}`; excerpt is the **joined `transcript[].text`** falling back to `title`; author is the first `attendees[].name`; timestamp is `created_at`.
- **Verification**: no verify — poll/passive; no webhook delivery, no signature.
- **Auth + transport (deferred live network)**: API key via env var (`GRANOLA_API_KEY`), `Authorization: Bearer <key>`; `GET https://public-api.granola.ai/v1/notes?include=transcript` (there is **no** `/transcripts` collection); cursor pagination (`cursor` + `hasMore`); `created_after` watermark. No live network this cycle.
- **Modes**: passive (REST poll with `created_after` watermark); no webhooks.
- **PII handling**: full transcript text (meeting content, attendee names) emitted; producer sensitive screen (`FX-SEC-001`) is the guard.
- **Drift corrected (was 2026-06-05)**: prior docs asserted host `api.granola.ai`, endpoint `/transcripts`, scalar `transcript_text`, `participants`, `ended_at`, `since` — all DRIFT vs the verified contract above.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
