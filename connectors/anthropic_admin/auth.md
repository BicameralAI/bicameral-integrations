# Anthropic Admin Auth

Auth model recorded for the live cycle; this connector ships the **parse surface** only
(live REST poll deferred).

- Default trust tier: T1 (read) / ACTIVE (poll).
- **No webhook**: the Usage & Cost API is poll-only (poll ≤ once/min) — no signed inbound
  surface and no `verify()`.
- **Active fetch auth (deferred)**: `GET /v1/organizations/usage_report/messages` (and
  `/cost_report`) require an **Admin API key** (`x-api-key: $ANTHROPIC_ADMIN_KEY`, starting
  `sk-ant-admin…`, admin-role-only) plus the `anthropic-version: 2023-06-01` header. Pagination
  via `has_more` + `next_page`; time buckets `1m`/`1h`/`1d`. Resolved by the operator runtime,
  never stored here.

## Privacy / PII

- The Usage & Cost surface is **aggregate and PII-free**: grouping dimensions are opaque ids
  (`workspace_id`, `api_key_id`), model names, and service tiers — no user email/name. The
  connector surfaces only token totals + models.
- **Per-user** cost/attribution is a separate, PII-bearing API (Claude Code Analytics) and is
  **deferred** behind the PII redaction-and-pass model. The `/cost_report` rich parse is deferred.

## Expected secret keys (operator runtime)

- `admin_api_key` — the org Admin API key (`x-api-key`) for the deferred REST poll.

## Deferred live paths

- Live REST poll of `/v1/organizations/usage_report/messages` (+ `/cost_report`) + admin-key
  resolution + `has_more`/`next_page` pagination.

Credentials are resolved by the operator runtime, never stored in this package.
See [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
