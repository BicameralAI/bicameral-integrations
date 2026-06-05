# Zendesk Connector — Canonical References

Single place tracking the canonical documentation links for the `zendesk` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | support / customer-success |
| Priority | P1 |
| Default trust tier | T1/T5 |
| Integration role | support-ticket / customer evidence |
| Readiness (lifecycle) | Beta (parse + Base64-HMAC webhook verify, proven end-to-end through the `runtime/` harness; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://developer.zendesk.com/api-reference/ticketing/introduction/ |
| Webhook/event | https://developer.zendesk.com/documentation/webhooks/ |
| Webhook verify | https://developer.zendesk.com/documentation/webhooks/verifying/ |
| Auth | https://developer.zendesk.com/api-reference/introduction/security-and-auth/ |

## Verified API/webhook contract (as built, 2026-06-05)

- **Ticket webhook event (parsed)**: `parse_ticket` reads `{type, id, time, detail.{id, subject, description, url, requester_id, updated_at, status, priority, via.channel}, event.type}`; ticket id from `detail.id` or parsed from `"zen:ticket:<id>"` subject; excerpt is `redact(subject) — redact(description)`.
- **Verification (built)**: `X-Zendesk-Webhook-Signature` = `base64(HMAC-SHA256(signing_secret, timestamp + body))` with companion `X-Zendesk-Webhook-Signature-Timestamp`; `verify()` calls `verify_zendesk_signature` (fail-closed, constant-time). Concatenation is `timestamp + body` with no separator; signature is Base64 (not hex). No anti-replay window; best-effort dedup on envelope `id` then `detail.id`.
- **Auth (deferred)**: per-webhook signing secret injected by operator runtime; REST API poll (`/api/v2`) with API token or OAuth deferred. No live network this cycle.
- **Modes**: webhook (primary) + active (REST fallback).
- **PII handling**: ticket subject + body (`detail.description`) emitted via **redact-and-pass** — `adapter.core.redaction.redact` scrubs secrets/PHI/PAN/email/phone to placeholders before emission. Comment threads and attachments excluded (first description only). Producer sensitive screen (`FX-SEC-001`) remains the fail-closed backstop.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [CS/support connectors research brief](../../docs/research-brief-cs-support-connectors-2026-06-04.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0012 readiness ladder + runtime boundary](../../docs/adr/0012-connector-readiness-ladder-and-live-ingest-runtime.md)
