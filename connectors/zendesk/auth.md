# Zendesk Connector — Auth & Live Ingest (DEFERRED)

The parse + signature-verify surface is implemented; the live boundary is
deferred to the operator runtime, consistent with every other connector.

## Webhook signature (IMPLEMENTED)

- Header `X-Zendesk-Webhook-Signature` = `base64(HMAC-SHA256(signing_secret,
  TIMESTAMP + BODY))`; companion `X-Zendesk-Webhook-Signature-Timestamp`.
- Concatenation is `timestamp + body` with **no separator**; the body may be
  empty (GET/DELETE → `b""`). Signature is **Base64**, not hex.
- Verified by `adapter.core.webhook_security.verify_zendesk_signature`
  (fail-closed, constant-time). Zendesk documents **no replay-timestamp
  window**, so best-effort dedup is the replay guard (the timestamp is inside
  the signed content and cannot be tampered).
- The signing secret is per-webhook: Admin Center → webhook details → *Reveal
  secret*, or `GET /api/v2/webhooks/{webhook_id}/signing_secret`. The operator
  runtime resolves and injects it (`ZendeskConnector(secret=...)`); it is never
  stored in this package.

## Deferred (operator runtime owns these)

- **Live HTTP receipt** of the webhook delivery.
- **REST poll / Events ingest** (`/api/v2`, API token or OAuth scopes, rate
  limits 200–2,500 req/min by plan).
- **Secret/keyring resolution.**
- **PII redaction-and-pass model for live ticket-body ingest.** Ticket bodies
  are customer-PII-dense. The producer sensitive screen (`FX-SEC-001`) HARD-
  screens (rejects) any emission containing secret/PHI/PAN — safe but
  reject-on-PII; before *live* ticket ingest, a redaction-and-pass model (strip
  PII, keep the rest) should land so support evidence flows without leaking PII.
  This connector deliberately scopes the excerpt to the ticket **subject** (low
  PII) and never the body, but live ingest must clear this gate first
  (catalog out-of-scope line: "connectors that require broad customer PII access
  before a redaction model exists").

## Out of scope (different repo)

- Ticket triage / reply / status writes — agent action at inference time belongs
  to `bicameral-mcp` (T3/T5), not this read-only evidence adapter (SG-2026-06-04-K).
