# Notion Connector — Canonical References

Single place tracking the canonical documentation links for the `notion` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | docs |
| Priority | P0 |
| Default trust tier | T1/T3 |
| Integration role | evidence + event |
| Readiness (lifecycle) | Beta -> **flip-ready, NOT yet Live** (parse + `X-Notion-Signature` verify; page title redact-and-passed, opaque created_by.id surfaced; FX-CFG-001 webhook descriptor shipped, contract re-verified live 2026-06-12). Open wire_gate: the `sha256=` prefix on X-Notion-Signature is UNVERIFIED (confirm live before Live; SG-2026-06-12-A). Webhook receipt operator-runtime; active fetch deferred. |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://developers.notion.com/reference/intro |
| Webhook/event | https://developers.notion.com/reference/webhooks |
| Auth | https://developers.notion.com/docs/authorization |
| Changelog/notes | https://developers.notion.com/page/changelog |

## Verified API/webhook contract (as built, 2026-06-05)

- **Page payload (parsed)**: `parse_page` reads `{id, url, properties, created_by.id, last_edited_time, created_time}`; title extracted via `_page_title` — walks `properties` values for the one whose `type == "title"`, joining `plain_text` of its rich-text array. Excerpt is title (page body/blocks are a separate fetch, deferred).
- **Verification (built)**: `X-Notion-Signature: sha256=<hex HMAC-SHA256(verification_token, raw_body)>`; `verify()` REQUIRES the `sha256=` prefix (bare hex rejected), strips it, calls `verify_hmac_hex` (fail-closed, constant-time). Dedup on `payload.id` then `payload.entity.id`.
- **Auth (deferred)**: Notion integration token or OAuth; `verification_token` for webhook subscription injected by operator runtime. No live network this cycle.
- **Modes**: active (Notion API page fetch) + webhook; both share `parse_page`.
- **PII handling**: page title emitted; `created_by.id` (user UUID, not display name) as author. Block content deferred. Producer sensitive screen (`FX-SEC-001`) is the guard.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
