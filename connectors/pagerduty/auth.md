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
  - **Spot-check pending (re-attempted 2026-06-08)**: the official
    `developer.pagerduty.com/docs/webhooks/webhook-signatures` page is **JS-rendered and
    machine-unfetchable** — automated verification could not capture an authoritative quote.
    The scheme (`X-PagerDuty-Signature`, `v1=` multi-sig, HMAC-SHA256 hex over the raw body)
    matches multiple non-authoritative corroborating sources but remains **UNVERIFIED against
    provider docs**. Confirm in a real browser before production reliance (BACKLOG; the one
    connector whose signature scheme is not doc-confirmed).

## Deferred live paths

- Live HTTP webhook receipt + secret/keyring resolution (the operator runtime
  injects the secret + dedup cache into the connector).
- REST API incident fetch (active fallback).

Credentials (webhook signing secret) are resolved by the operator runtime,
never stored in this package. See [references.md](references.md) and
[TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
