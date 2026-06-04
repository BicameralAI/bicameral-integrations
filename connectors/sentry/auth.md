# Sentry Auth

Auth model recorded for the live cycle; this connector ships the **parse
surface** only.

- Default trust tier: T1 (read API) / WEBHOOK.
- Auth: webhook delivery verified via `Sentry-Hook-Signature` = HMAC-SHA256 of
  the **raw request body** (hex) with the integration client secret.
  **Implemented**: `SentryConnector.verify()`/`normalize_event()` reuse
  `adapter.core.webhook_security.verify_hmac_hex` — fail-closed + constant-time.
  - **Raw-body decision**: the official JS reference signs
    `JSON.stringify(request.body)`; we HMAC the **raw received bytes** to avoid
    serializer mismatch. Add an integration test against a real delivery.
  - **No replay-timestamp window** is documented by Sentry, so best-effort
    delivery dedup (on a `Request-ID`/issue id when present — never drops an
    id-less event) is the only replay guard.

## Deferred live paths

- Live HTTP webhook receipt + secret/keyring resolution (the operator runtime
  injects the secret + dedup cache into the connector).
- REST API issue fetch (active fallback).

Credentials (integration client secret) are resolved by the operator runtime,
never stored in this package. See [references.md](references.md) and
[TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
