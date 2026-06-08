# Fathom Auth

Credentials are declared here but resolved by the operator runtime at the live
cycle, not by repository-local config. This cycle ships the parse surface only;
the items below are recorded so the live integration inherits them.

## REST (passive poll)

- Base URL: `https://api.fathom.ai/external/v1`.
- Auth: API key generated in the Fathom settings area, sent on each request.
- Rate limit: 60 calls / 60 s; honor `RateLimit-Limit` / `RateLimit-Remaining`
  / `RateLimit-Reset` response headers.
- Listing: `GET /meetings`, cursor pagination (`next_cursor` → `cursor`),
  time-window filters (`created_after` / `created_before`); transcript /
  summary / action-items are opt-in expansions (default off).

## Webhook (`new-meeting-content-ready`)

- Signing: Standard Webhooks / Svix. Headers `webhook-id`, `webhook-timestamp`
  (epoch **seconds**), `webhook-signature` (base64, space-delimited versioned
  signatures, e.g. `v1,<b64>`).
- Secret: prefixed `whsec_`; verification is
  `HMAC-SHA256(base64decode(secret), "${id}.${timestamp}.${body}")`, base64,
  constant-time compare. Reuse a Svix-style verifier — do not hand-roll.
- **Verified 2026-06-08 (developers.fathom.ai/webhooks)**: the header set + `whsec_`
  base64-decoded secret + `{id}.{timestamp}.{body}` signed content + base64 `v1,<b64>`
  signatures all match exactly. Attribution notes: Fathom's own docs describe these
  mechanics but do **not** name "Svix"/"Standard Webhooks" (the brand is inferred from the
  byte-identical scheme), and the 300 s replay tolerance is the Standard-Webhooks **default**
  (not Fathom-documented — reconcile if Fathom publishes a specific window).

## Verification (this cycle)

`FathomConnector(secret=..., dedup=..., clock=...)` now implements `verify` +
`normalize_event` over the Svix scheme above (see `adapter/core/webhook_security.py`).
The signing secret is **injected**; keyring resolution stays in the operator
runtime. Residual risks the operator owns:

- **TLS is mandatory.** Replay beyond the dedup TTL (default 24 h) is bounded
  only by TLS — terminate webhooks behind HTTPS.
- **Multi-process dedup is not shared.** The in-memory `DeliveryDedupCache` is
  per-process; a load-balanced multi-process deployment can process the same
  delivery once per process. A shared cache (Redis, etc.) is out of scope.

The live HTTP boundary remains deferred (operator runtime).
