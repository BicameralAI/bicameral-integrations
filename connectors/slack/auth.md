# Slack Auth

Stage: **flip-ready** — `verify()` is built and proven through the `runtime/` harness
(the prior "Candidate / no live implementation yet" note was stale; corrected deep-audit Cycle 5).

- Default trust tier: T2/T3
- Auth: https://docs.slack.dev/authentication/

## Verification

`SlackConnector.verify()` reuses `adapter.core.webhook_security.verify_slack_signature`:
`X-Slack-Signature: v0=<hex HMAC-SHA256(signing_secret, "v0:{X-Slack-Request-Timestamp}:{raw_body}")>`
with a **5-minute replay window** on the timestamp — fail-closed + constant-time, over the **raw
received bytes** (verify before parse). The `url_verification` handshake and unverified deliveries
normalize to `[]`. Expected secret key: `webhook_secret` (the Slack signing secret). The live
Events-API HTTP receipt + secret resolution stay in the operator runtime.

Credentials are resolved by the operator runtime, never stored in this package.
See [references.md](references.md) and [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
