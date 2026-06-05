# Confluence Auth

Auth model recorded for the live cycle; this connector ships the **parse surface**
only (live HTTP receipt, REST fetch, and webhook verification deferred).

- Default trust tier: T1 (read) / T3 (proposed writes, far future) / ACTIVE+WEBHOOK.
- **Webhook verification (DEFERRED — intentionally not shipped this cycle)**:
  Confluence **Cloud** webhooks are delivered through the Connect/app framework and
  have **no payload-signature scheme confirmable from current Atlassian docs**. The
  HMAC `X-Hub-Signature` (HMAC-SHA256, secret-keyed) scheme documented for
  Confluence **Data Center / Server** does **not** transfer to Cloud. Per
  verify-before-cite, no `verify()` is built on this uncertain ground; the
  connector is proven through the poll/active parse path instead.
  - When the Cloud signature contract is verified (or a Data-Center deployment is
    targeted), an HMAC verifier would reuse
    `adapter.core.webhook_security.verify_hmac_hex` over the raw body.
- **Active fetch auth (deferred)**: Confluence Cloud REST uses OAuth 2.0 (3LO) or
  an API token with HTTP Basic; Connect apps use a JWT (`qsh`). None are wired here.

## Expected secret keys (operator runtime)

- `api_email` + `api_token` — HTTP Basic for the deferred REST content fetch.
- `oauth_*` — OAuth 2.0 (3LO) credentials for the deferred app path.

## Deferred live paths

- Live HTTP webhook receipt + (once contractually verified) signature verification.
- REST `GET /wiki/rest/api/content/{id}?expand=body.storage` active fetch + pagination.

Credentials are resolved by the operator runtime, never stored in this package.
See [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
