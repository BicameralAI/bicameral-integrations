# Fathom Auth

Credentials are declared here but resolved by the operator runtime at the live
cycle, not by repository-local config. This cycle ships the parse surface only;
the items below are recorded so the live integration inherits them.

## REST (passive poll)

- Base URL: `https://api.fathom.ai/external/v1`.
- Auth: API key generated in the Fathom settings area, sent on each request as the
  **`X-Api-Key`** header (verified 2026-06-12, developers.fathom.ai/api-reference).
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
- **Re-verified 2026-06-12 (developers.fathom.ai/webhooks)**: the header set + `whsec_`
  base64-decoded secret + `{id}.{timestamp}.{body}` signed content + base64 `v1,<b64>`
  signatures all match exactly. Fathom's docs still do **not** name "Svix"/"Standard Webhooks"
  (the brand is inferred from the byte-identical scheme), but the replay tolerance is now
  **Fathom-documented as "within 5 minutes" (300 s)** — no longer an inferred Standard-Webhooks
  default.

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

## Sensitivity / PII

The transcript carries spoken content (potential secrets/PII) and `transcript[].speaker.display_name`
real names. `parse_meeting` (2026-06-12, flip cycle):

- **drops the speaker + recorder real names** — identity minimization covers a name the connector
  would INJECT into emitted text, not just the `author` slot (SG-2026-06-12-H); honors the platform's
  "human real names are dropped" guarantee.
- **redact-and-passes** the transcript + summary + title (scrubs secret/PHI/PAN + email/phone),
  matching the granola/devin free-text standard. `FX-SEC-001` is the un-bypassable secret/PHI/PAN
  backstop. No credential or secret is stored in this package.
