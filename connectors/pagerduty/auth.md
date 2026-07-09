# PagerDuty Auth

Auth model recorded for the live cycle; this connector ships the **parse
surface** only.

- Default trust tier: T1 (read API) / WEBHOOK.
- Auth: webhook delivery verified via `X-PagerDuty-Signature` = HMAC-SHA256 of
  the **raw body** (hex), as a **comma-separated `v1=…,v1=…` set** for
  zero-downtime key rotation. **Implemented**: `PagerDutyConnector.verify()`/
  `normalize_event()` use the new `adapter.core.webhook_security.verify_hmac_hex_multi`
  (accept if ANY `v1=` candidate matches; fail-closed + constant-time).
  - **No replay-timestamp window** is documented, so best-effort delivery dedup
    (on the envelope `event.id` when present — never drops an id-less event) is
    the only replay guard.
  - **Spot-check CONFIRMED first-party (2026-07-08, real-browser render; closes BACKLOG B8)**:
    the official page — now at `developer.pagerduty.com/docs/verifying-webhook-signatures`
    (the old `/docs/verifying-signatures` slug 404s) — confirms every implemented detail:
    `X-PagerDuty-Signature` carries one or MORE comma-separated signatures (zero-downtime
    secret rotation), current version `v1=` + HMAC-SHA256 of the **raw body** with the shared
    secret, **Base16 (hex)** encoded, accept if **at least one** matches, compare in
    **constant time**, verify against the unaltered raw body with UTF-8 encoding. The scheme
    is now doc-confirmed like every other connector.

## Deferred live paths

- Live HTTP webhook receipt + secret/keyring resolution (the operator runtime
  injects the secret + dedup cache into the connector).
- REST API incident fetch (active fallback).

Credentials (webhook signing secret) are resolved by the operator runtime,
never stored in this package. See [references.md](references.md) and
[TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
