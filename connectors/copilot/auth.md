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

## Live path — reference poll client (recorded-fixture-proven)

The request-construction is **built** in `runtime/poll_specs.py` (`build_copilot_spec`) and proven
against a recorded fixture (`Authorization: Bearer` + `Accept` + `X-GitHub-Api-Version`; the response
is a **top-level JSON array** of day objects → one emission per day). The real network call + token
resolution remain operator-run.

- **Secret resolver key**: the `SecretResolver` resolves by the connector **`source_id`** (`copilot`);
  `api_token` above is the credential's *meaning*.
- **Verified (docs.github.com 2026-06-08)**: the endpoint paginates by `page`/`per_page` (max 100;
  lookback is **100 days**, not 28) — wired via `PageNumberPager` (stop-on-short-page); the top-level
  array shape is confirmed. The `X-GitHub-Api-Version` value (`2022-11-28`) is valid (EOL 2028-03-10;
  latest is `2026-03-10`) and is an argument, not baked as fact. *(Earlier "no pagination, date-range
  bounded" was DRIFT — the 28-day figure is the dashboard window, not the API cap.)*

## Deferred live paths

- Live REST poll of `GET /orgs/{org}/copilot/metrics` (+ enterprise/team scopes) + token resolution
  (the `runtime/` poll client is built; the operator supplies the live transport + secret).
- The per-user NDJSON usage-metrics report path (gated on the PII redaction-and-pass model).

Credentials are resolved by the operator runtime, never stored in this package.
See [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
