# GitLab Auth

Auth model recorded for the live cycle; this connector ships the **parse +
verify surface** (live HTTP receipt + REST fetch deferred).

- Default trust tier: T1 (read) / T3 (proposed writes, far future) / WEBHOOK.
- **Webhook verification (implemented)**: GitLab webhooks authenticate with a
  **plaintext shared-secret token**, not an HMAC over the body. The configured
  secret is sent verbatim in the `X-Gitlab-Token` header; the receiver compares
  it constant-time to the configured secret and rejects on mismatch.
  `GitLabConnector.verify()` delegates to
  `adapter.core.webhook_security.verify_shared_token` — fail-closed
  (missing secret, missing/blank header, or mismatch all reject) and
  constant-time (`hmac.compare_digest`). The error message never contains the
  token or secret value.
  - **No anti-replay timestamp window**: the token is a static shared secret with
    no signed timestamp, so best-effort delivery dedup (on `X-Gitlab-Event-UUID`)
    is the only replay guard; TLS + dedup-TTL are operator residual risks.
  - **Deferred — Standard-Webhooks signing token**: newer GitLab webhooks can be
    configured with a *signing token* that produces an HMAC-SHA256 signature over
    `webhook-id.webhook-timestamp.body` with `webhook-signature` headers (the same
    Svix / Standard-Webhooks scheme `connectors/fathom` implements via
    `verify_standard_webhook`). Not wired this cycle; when enabled it is the
    stronger path (authenticity + integrity + replay window) and can reuse the
    existing Svix verifier.

## Expected secret keys (operator runtime)

- `webhook_token` — the configured `X-Gitlab-Token` secret (`verify()`).
- `api_token` — a personal/project/group access token for the deferred REST fetch.

## Deferred live paths

- Live HTTP webhook receipt + secret/keyring resolution (the operator runtime
  injects the secret + dedup cache into the connector).
- REST active fetch of merge requests / issues (same `object_attributes` shape).

Credentials are resolved by the operator runtime, never stored in this package.
See [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
