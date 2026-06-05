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
- **Secret/keyring resolution.**

## PII / ticket body (IMPLEMENTED — redact-and-pass, Entry #84)

Ticket bodies are customer-PII-dense. The excerpt now emits the ticket **subject plus
the body** (`detail.description`) passed through `adapter.core.redaction.redact`
(**redact-and-pass**: secret/PHI/PAN + email/phone scrubbed to placeholders), so support
evidence flows without leaking PII; the producer sensitive screen (`FX-SEC-001`) remains
the fail-closed backstop (`detect_sensitive(redact(x)) == []` by construction). This
replaces the earlier subject-only posture — the redaction-and-pass model that was the gate
for live ticket-body ingest is now built (`adapter/core/redaction.py`). Comment threads /
attachments remain out of scope (the first `description` only).

## Out of scope (different repo)

- Ticket triage / reply / status writes — agent action at inference time belongs
  to `bicameral-mcp` (T3/T5), not this read-only evidence adapter (SG-2026-06-04-K).
