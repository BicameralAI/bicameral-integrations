# Linear Auth

Credentials are declared here but resolved by the operator runtime at the live
cycle, not by repository-local config. This cycle ships the parse surface only;
the items below are recorded so the live integration inherits them.

## GraphQL (active fallback)

- Endpoint: `https://api.linear.app/graphql`.
- Auth: personal API key sent in the `Authorization` header (created in
  Settings > Security & Access). OAuth is an alternative for multi-workspace.

## Webhook (primary)

- Configured in Settings > Administration > API (admin permission).
- Payload envelope: `action` (`create`/`update`/`remove`), `type`
  (`Issue`/`Comment`/...), `actor`, `createdAt`, `data`, `url`, `updatedFrom`
  (prior values, update only), `webhookId`, `webhookTimestamp` (UNIX ms),
  `organizationId`.
- Signing: `Linear-Signature` header = **hex** HMAC-SHA256 of the **raw**
  request body using the webhook signing secret.
- Anti-replay: reject when `abs(now − webhookTimestamp) > 60000 ms`.

## Verification (this cycle)

`LinearConnector(secret=..., dedup=..., clock=...)` now implements `verify` +
`normalize_event`: hex HMAC over the raw body **first**, then the 60 s
`webhookTimestamp` window (see `adapter/core/webhook_security.py`). The signing
secret is **injected**; keyring resolution stays in the operator runtime.
Residual risks the operator owns:

- **TLS is mandatory.** Replay beyond the dedup TTL is bounded only by TLS plus
  the 60 s timestamp window — terminate webhooks behind HTTPS.
- **Multi-process dedup is not shared.** The in-memory `DeliveryDedupCache` is
  per-process; a shared cache is out of scope.

The live GraphQL fetch + HTTP boundary remain deferred (operator runtime).
