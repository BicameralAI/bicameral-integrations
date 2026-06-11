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
| Readiness (lifecycle) | Beta -> **flip-ready, NOT yet Live** (webhook `parse_event` → page-changed pointer keyed by `entity.id`; `X-Notion-Signature` verify + body-hash dedup; FX-CFG-001 webhook descriptor shipped; contract DOC-verified 2026-06-08, re-confirmed brief #143 — NOT live-verified). Open wire_gate: the `sha256=` prefix on X-Notion-Signature is UNVERIFIED (confirm live before Live; SG-2026-06-12-A). Webhook delivery is a page-id POINTER (no content); page-title redact-and-pass + active fetch deferred; receipt operator-runtime. |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://developers.notion.com/reference/intro |
| Webhook/event | https://developers.notion.com/reference/webhooks |
| Auth | https://developers.notion.com/docs/authorization |
| Changelog/notes | https://developers.notion.com/page/changelog |

## Verified API/webhook contract (as built, 2026-06-05)

- **Webhook envelope (parsed, live mode)**: `parse_event` reads the delivery envelope `{id (event id), type, entity:{id,type}, timestamp}` — which carries NO page content — and emits a page-changed POINTER keyed by the page `entity.id` (the stable subject, NOT the ephemeral event id), title `Notion <event_type>`. Corrected 2026-06-12 (deep-audit HIGH): the prior `parse_page(payload)` on the raw envelope captured the event UUID as ref and was masked by a fabricated full-page fixture (SG-2026-06-12-C, fixture-proven != contract-correct).
- **Page payload (parsed, deferred active fetch)**: `parse_page` reads a full page object `{id, url, properties, created_by.id, last_edited_time, created_time}`; title via `_page_title` (walks `properties` for `type == "title"`, joins `plain_text`); `id` is `str`-coerced. Fed by the deferred `pages.retrieve` keyed by `entity.id`.
- **Verification (built)**: `X-Notion-Signature: sha256=<hex HMAC-SHA256(verification_token, raw_body)>`; `verify()` REQUIRES the `sha256=` prefix (bare hex rejected), strips it, calls `verify_hmac_hex` (fail-closed, constant-time). Dedup on the event `id` with a `sha256(body)` fallback (a signed id-less body cannot bypass dedup).
- **Auth (deferred)**: Notion integration token or OAuth; `verification_token` for webhook subscription injected by operator runtime. No live network this cycle.
- **Modes**: webhook (`parse_event`, live) + active Notion API page fetch (`parse_page`, deferred); the two surfaces parse DIFFERENT shapes (envelope vs full page).
- **PII handling**: webhook pointer carries only the opaque `entity.id` (no free-text). Deferred active fetch: page title redact-and-passed; `created_by.id` (user UUID, not display name) as author. Producer sensitive screen (`FX-SEC-001`) is the un-bypassable guard.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
