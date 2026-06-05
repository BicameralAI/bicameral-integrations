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

## Deferred live paths

- Live REST poll of `/v3/organizations/{org}/sessions` (+ `/messages`) + Bearer key resolution + cursor pagination.

Credentials are resolved by the operator runtime, never stored in this package.
See [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
