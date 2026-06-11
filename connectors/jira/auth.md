# Jira Auth

Auth model recorded for the live cycle; this connector ships the **parse +
verify surface** (live HTTP receipt + REST fetch deferred).

- Default trust tier: T1 (read) / T3 (proposed writes, far future) / WEBHOOK.
- **Webhook verification (implemented)**: classic Jira Cloud webhooks with a
  configured secret sign delivery `X-Hub-Signature: sha256=<hex-HMAC-SHA256(
  secret, raw_body)>` (WebSub). `JiraConnector.verify()` strips the `sha256=`
  prefix and reuses `adapter.core.webhook_security.verify_hmac_hex` — fail-closed
  + constant-time, over the **raw received bytes** (verify before parse).
  - **No anti-replay timestamp window** is documented by Atlassian, so
    best-effort delivery dedup (on `X-Atlassian-Webhook-Identifier`, then
    `issue.id`) is the only replay guard; TLS + dedup-TTL are operator residual
    risks (weaker than Linear's signed 60s window).
  - **Deferred auth paths**: Connect apps (HS256/RS256 JWT with `qsh`), Forge,
    and Automation-for-Jira webhooks use their own platform auth, not
    `X-Hub-Signature` — not implemented this cycle.

## Verification

`JiraConnector.verify()` checks `X-Hub-Signature: sha256=<hex HMAC-SHA256(webhook_secret,
raw_body)>` (WebSub `method=signature`): strips the `sha256=` prefix and reuses
`adapter.core.webhook_security.verify_hmac_hex` — fail-closed + constant-time, over the **raw
received bytes** (verify before parse). No Atlassian-documented anti-replay window, so best-effort
dedup (on `X-Atlassian-Webhook-Identifier`, then `issue.id`) is the only replay guard (see above).

## Expected secret keys (operator runtime)

- `webhook_secret` — the configured webhook signing secret (`verify()`).
- `api_email` + `api_token` — HTTP Basic for the deferred REST fetch (or OAuth 2.0 3LO).

## Deferred live paths

- Live HTTP webhook receipt + secret/keyring resolution (the operator runtime
  injects the secret + dedup cache into the connector).
- REST `GET /rest/api/3/issue/{idOrKey}` active fetch (same ADF `fields` shape).

Credentials are resolved by the operator runtime, never stored in this package.
See [references.md](references.md) and [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
