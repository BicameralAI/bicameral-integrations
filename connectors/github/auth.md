# GitHub Auth

Credentials are declared here but stored by the core operator runtime, not in
repository-local config.

Expected secret keys:

- `api_key`
- `webhook_secret`

## Verification

- **Webhook verification (implemented)**: GitHub signs deliveries
  `X-Hub-Signature-256: sha256=<hex HMAC-SHA256(webhook_secret, raw_body)>`.
  `GitHubConnector.verify()` strips the `sha256=` prefix and reuses
  `adapter.core.webhook_security.verify_hmac_hex` — fail-closed + constant-time,
  over the **raw received bytes** (verify before parse).
- **Replay dedup**: on the per-delivery `X-GitHub-Delivery` GUID, with a
  `sha256(body)` fallback so an empty/absent delivery header cannot bypass dedup
  (deep-audit Cycle 4). GitHub documents no timestamp in the signed content, so
  the dedup-cache TTL + TLS are the residual replay guard.
- **Deferred**: the live HTTP receipt + REST active-fetch auth (`api_key`).

