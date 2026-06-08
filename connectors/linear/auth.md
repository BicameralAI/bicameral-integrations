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

## GraphQL active fetch (built this cycle — FX-LINEAR-003)

Verified against linear.app/developers (2026-06-08): **POST** `https://api.linear.app/graphql`,
`Content-Type: application/json`, body `{"query","variables"}`. **Auth: personal API key in
`Authorization: <API_KEY>` — raw key, NO `Bearer` prefix** (OAuth tokens would use `Bearer`).
Pagination is Relay cursor (`first`/`after`, default 50); envelope
`data.issues.{nodes, pageInfo{hasNextPage, endCursor}}`. `runtime.graphql_poll.poll_graphql` +
`poll_specs.build_linear_graphql_spec` + `connector.parse_issue_node` implement the fetch; the
secret is resolved by `source_id="linear"` and the **HTTP boundary stays operator-run** (a recorded
transport proves the path; a mock does not promote to Live — ADR-0012).

**Wire-gate (UNVERIFIED until a live response, verify-before-cite):** the exact Issue field set
queried (`id`/`identifier`/`title`/`description`/`url`/`updatedAt`/`state.name`) and that default
`orderBy: updatedAt` suits incremental fetch. Fail-closed semantics ARE confirmed by tests: a 200
carrying a GraphQL `errors` array does NOT emit; rate-limiting (**HTTP 400 + `errors[].code==
"RATELIMITED"`**, not 429) raises backpressure; oversized body, non-list nodes, and a runaway cursor
all fail closed. Rate limits (API key): 5,000 req/hr, 3M complexity pts/hr, 10k single-query max.
