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

## Live path — reference poll client (recorded-fixture-proven)

The request-construction + pagination half of the live poll is now **built** in
`runtime/poll_client.py` (`build_anthropic_admin_spec` + `poll`) and proven end-to-end against
recorded response fixtures (`x-api-key` + `anthropic-version` headers; `has_more`+`next_page`
pagination; bucket parse → emission; PII-free). The **real network call + admin-key resolution
remain operator-run** (a recorded-fixture test does not promote this connector to Live; ADR-0012).

**Assumptions to confirm against live Anthropic docs BEFORE wiring to the real network**
(verify-before-cite — a recorded-fixture test cannot discharge these; a mock returns whatever is
queued):

- **A1 — response envelope key.** The poll client assumes the time buckets arrive under a top-level
  `data` list (`response_json["data"]`). Our verified sources document the *bucket* shape, not the
  envelope key. `PollSpec.items` is a config callable, so confirming/adjusting this is a one-liner.
- **A2 — page-token transport + param name.** The client assumes `next_page` is sent back as a query
  parameter named `page`. The param **name and transport (query vs body vs header) are unverified.**
  `build_anthropic_admin_spec(..., next_param=...)` parameterizes it.

## Deferred live paths

- The real-network REST poll of `/v1/organizations/usage_report/messages` (+ `/cost_report`) +
  admin-key resolution (the `runtime/` poll client is built; the operator supplies the live
  transport + secret + A1/A2 confirmation).

Credentials are resolved by the operator runtime, never stored in this package.
See [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
