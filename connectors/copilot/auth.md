# GitHub Copilot Auth

Auth model recorded for the live cycle; this connector ships the **parse surface** only
(live REST poll deferred).

- Default trust tier: T1 (read) / ACTIVE (poll).
- **No webhook**: GitHub publishes no webhooks for Copilot metrics — ingestion is an
  outbound REST poll, so there is no signed inbound surface and no `verify()`.
- **Active fetch auth (deferred)**: `GET /orgs/{org}/copilot/metrics` (and the enterprise/team
  scopes) requires an OAuth app token or PAT with `manage_billing:copilot` **or** `read:org` /
  `read:enterprise`. Resolved by the operator runtime, never stored here.
- **Privacy**: the aggregate metrics object contains no per-developer identity. The newer
  per-user NDJSON "usage metrics" report API is **deferred** (per-user PII → future
  redaction-and-pass model). The legacy Copilot "usage" API was closed 2026-04-02 and is not used.

## Expected secret keys (operator runtime)

- `api_token` — OAuth/PAT with `manage_billing:copilot` or `read:org` for the deferred REST poll.

## Deferred live paths

- Live REST poll of `GET /orgs/{org}/copilot/metrics` (+ enterprise/team scopes) + token resolution.
- The per-user NDJSON usage-metrics report path (gated on the PII redaction-and-pass model).

Credentials are resolved by the operator runtime, never stored in this package.
See [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
