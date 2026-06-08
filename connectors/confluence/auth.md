# Confluence Auth

Auth model recorded for the live cycle; this connector ships the **parse surface**
only (live HTTP receipt, REST fetch, and webhook verification deferred).

- Default trust tier: T1 (read) / T3 (proposed writes, far future) / ACTIVE+WEBHOOK.
- **Webhook verification (DEFERRED — corrected rationale, verified 2026-06-08)**:
  Confluence **Cloud** webhooks DO carry a verifiable authentication scheme, but it is
  **Connect-app JWT**, NOT an HMAC payload signature: each webhook POST includes
  `Authorization: JWT <token>`, signed **HS256** over the per-tenant install **shared
  secret**, with a `qsh` (query-string-hash) binding the token to the request
  method+path (developer.atlassian.com). The Data-Center/Server HMAC `X-Hub-Signature`
  scheme does **not** transfer to Cloud (confirmed). So the connector's earlier claim
  that Cloud has "no confirmable signature scheme" was **too strong** — a scheme is
  documented and buildable. `verify()` stays deferred for the **correct** reason: the
  JWT path requires a **registered Connect app + the install-handshake shared-secret
  store** (per-tenant `clientKey`→secret) and a **JWT/qsh verifier** (`verify_hmac_hex`
  over the raw body is the WRONG primitive). When an operator runs a Connect app, build
  an HS256 JWT verifier + qsh recompute; until then it is correctly unbuilt.
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
