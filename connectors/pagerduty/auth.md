# PagerDuty Auth

Auth model recorded for the live cycle; this connector ships the **parse
surface** only.

- Default trust tier: T1 (read API) / WEBHOOK.
- Auth: webhook delivery verified via `X-PagerDuty-Signature` (HMAC-SHA256).
  **Key-rotation wrinkle**: the header carries **multiple comma-separated
  versioned signatures**, so the deferred `verify()` must check membership
  against any valid signature, not a single equality.

## Deferred live paths

- Webhook receipt + `X-PagerDuty-Signature` multi-signature verification +
  delivery dedup (mirror the Linear `verify()`/`normalize_event()` pattern,
  extended for the comma-separated rotation set).
- REST API incident fetch (active fallback).

Credentials (webhook signing secret) are resolved by the operator runtime,
never stored in this package. See [references.md](references.md) and
[TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
