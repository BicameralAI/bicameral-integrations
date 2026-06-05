# Google Drive / Docs Connector — Canonical References

Single place tracking the canonical documentation links for the `google_drive` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | docs |
| Priority | P1 |
| Default trust tier | T1/T3 |
| Integration role | evidence |
| Readiness (lifecycle) | Beta (proven end-to-end through the `runtime/` harness against a reference sink; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://developers.google.com/drive/api/guides/about-sdk |
| Webhook/event | https://developers.google.com/workspace/drive/api/guides/push |
| Auth | https://developers.google.com/identity/protocols/oauth2 |
| Changelog/notes | https://developers.google.com/workspace/drive/api/release-notes |

## Verified API/webhook contract (as built, 2026-06-05)

- **Document payload (parsed)**: `parse_document` reads a `documents.get` response — `{documentId, title, body.content}`; `extract_document_text` walks `body.content` flattening paragraphs (with Markdown heading decoration from `namedStyleType`) and table cells; excerpt is full document text falling back to title.
- **URL parsing**: `parse_gdrive_url` extracts the document id from `docs.google.com/document/d/<id>` or `drive.google.com/file/d/<id>` URLs (regex, 25–128 char alphanum id).
- **Verification**: no verify — webhook channel notifications deferred; no live delivery this cycle.
- **Auth (deferred)**: OAuth token JSON + refresh token; scopes `documents.readonly` + `drive.metadata.readonly`; live `documents.get` call deferred. No live network this cycle.
- **Modes**: active (URL fetch) + passive (folder poll) + webhook (Drive channel push) — only active parse surface ships this cycle; folder poll and channel webhooks deferred.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
