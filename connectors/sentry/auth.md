# Sentry Auth

Auth model recorded for the live cycle; this connector ships the **parse
surface** only.

- Default trust tier: T1 (read API) / WEBHOOK.
- Auth: webhook delivery verified via `Sentry-Hook-Signature` (HMAC-SHA256 of
  the raw body with the integration client secret). **Confirm-before-live**: the
  exact header/algorithm is unverified — verify against the Sentry integration-
  platform webhook docs before implementing `verify()`.

## Deferred live paths

- Webhook receipt + `Sentry-Hook-Signature` verification + delivery dedup
  (mirror the Linear `verify()`/`normalize_event()` HMAC + replay pattern).
- REST API issue fetch (active fallback).

Credentials (integration client secret) are resolved by the operator runtime,
never stored in this package. See [references.md](references.md) and
[TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
