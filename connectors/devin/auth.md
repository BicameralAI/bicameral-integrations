# Devin Auth

Auth model recorded for the live cycle; this connector ships the **parse + redaction
surface** only (live REST poll deferred).

- Default trust tier: T1 (read) / ACTIVE (poll).
- **No webhook**: Devin publishes no webhooks — ingestion is an outbound REST poll, so there
  is no signed inbound surface and no `verify()`.
- **Active fetch auth (deferred)**: the v3 API uses **Bearer** authorization with a
  **Service-User API key** (`cog_…`, shown once at creation, RBAC-scoped) or a Personal Access
  Token (PATs "coming soon"). Base `https://api.devin.ai/v3/`; `GET /v3/organizations/{org}/sessions`
  (list) and `GET /v3/enterprise/sessions/{devin_id}/messages` (deferred richer surface).
  Resolved by the operator runtime, never stored here.

## Privacy / PII

- Session free-text (`title`, `structured_output`, message bodies) may carry secrets/PII, so it
  is passed through `adapter.core.redaction.redact` (scrubs secret/PHI/PAN + email/phone). FX-SEC-001
  remains the un-bypassable backstop.
- **`pull_request.url` is kept un-redacted** as the artifact location — consistent with the
  github/gitlab/jira connectors. A username embedded in a repo URL is the artifact path, not
  free-text evidence PII.
- The `/messages` endpoint (full per-message trail) is a deferred richer surface.

## Expected secret keys (operator runtime)

- `api_token` — the Service-User `cog_…` key (Bearer) for the deferred REST poll.
- `org_id` — the Devin organization id for the list endpoint.

## Live path — reference poll client (contract verified 2026-06-08 against docs.devin.ai)

The request-construction is **built** in `runtime/poll_specs.py` (`build_devin_spec`) and proven
against recorded fixtures. The real network call + token resolution remain operator-run.

- **Secret resolver key**: the `SecretResolver` resolves by the connector **`source_id`** (`devin`);
  `api_token` above is the credential's *meaning*. `org_id` is **not** resolved as a secret — the
  operator templates it into the required `base_url` (`build_devin_spec(resolver, base_url=…)` has no
  default, e.g. `https://api.devin.ai/v3/organizations/<org_id>/sessions`).
- **Verified contract** (docs.devin.ai / docs.devinenterprise.com): the session list wraps under
  **`items`** (NOT `sessions`); each session carries **`pull_requests`** (array of `{pr_url,
  pr_state}`), NOT a singular `pull_request.url`; cursor pagination is documented — response
  `end_cursor` + `has_next_page`, re-sent as query param `after` (wired via `PageToken`). The
  earlier `sessions`/`pull_request.url`/deferred-pagination assumptions were DRIFT (would have
  ingested zero live) and are corrected.

## Deferred live paths

- Live REST poll pagination of `/v3/organizations/{org}/sessions` (cursor) + the `/messages` richer
  surface + token resolution (the `runtime/` poll client fetches the first page; the operator
  supplies the live transport + secret + cursor confirmation).

Credentials are resolved by the operator runtime, never stored in this package.
See [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
