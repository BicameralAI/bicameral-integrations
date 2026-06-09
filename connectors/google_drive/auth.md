# Google Drive Auth

Credentials are declared here but stored by the core operator runtime, not in
repository-local config.

Expected credential material:

- OAuth token JSON
- refresh token when granted

Expected scopes (verified 2026-06-08, developers.google.com/docs/api):

- `https://www.googleapis.com/auth/documents.readonly` — valid for `documents.get`.
- `https://www.googleapis.com/auth/drive.readonly` (or `drive.file`) — for Drive access.
  **NOTE (drift corrected):** `drive.metadata.readonly` is **NOT** an accepted scope for the Docs
  `documents.get` call (the official authorization-scopes list is `documents`, `documents.readonly`,
  `drive`, `drive.readonly`, `drive.file`); use `drive.readonly`/`drive.file` for the live fetch.
  (`drive.metadata.readonly` is valid only for the separate Drive `files.get` metadata path.)

## Live fetch (built this cycle — FX-GDRIVE-002)

Verified developers.google.com/docs/api (2026-06-08): **`GET https://docs.googleapis.com/v1/documents/{documentId}`**;
response is a `Document` object (`documentId`/`title`/`body`). Auth: **`Authorization: Bearer <access_token>`**.
`runtime.doc_fetch.fetch_document` + `poll_specs.build_google_drive_spec(resolver, document_id=...)` implement
the fetch — a single GET (not paginated). The `document_id` is **`re.fullmatch`-validated** (`[A-Za-z0-9_-]{1,200}`)
before the URL splice (path/URL-injection guard); the body is capped + **dict-only** parsed (the connector parse
is non-self-guarding); FX-SEC-001 screens the (untrusted, possibly PII-dense) doc text via `normalize`.

**OAuth boundary:** the `SecretResolver` returns a **valid access token** for `source_id="google_drive"`; the
authorization-code grant + **token refresh stay operator-runtime** (our code only sets the Bearer header). The
HTTP boundary is operator-run (a recorded transport proves the path; a mock does NOT promote to Live — ADR-0012).

**Wire-gate (verify-before-cite, before the flip):** (1) the Bearer-header assumption confirmed against a live
401/200; (2) **multi-tab docs** — `extract_document_text` walks the legacy `body` only, so a multi-tab document
(content under `tabs[].documentTab.body`) emits **title-only** evidence (not a crash; `includeTabsContent`/`tabs[]`
deferred). Folder polling (Drive `files.list`) + push-notification webhooks remain deferred.

## OAuth credential facts (verified 2026-06-08 — research brief #125)

- **Access token: short-lived** (~1 h; the token response carries `expires_in` — honor it, do not hardcode).
  Source: developers.google.com/identity/protocols/oauth2/web-server.
- **Refresh-token exchange = plain form POST, NO signing:** `POST https://oauth2.googleapis.com/token`,
  `Content-Type: application/x-www-form-urlencoded`, `grant_type=refresh_token` + `client_id` +
  `client_secret` + `refresh_token` → `{access_token, expires_in}`. **Stdlib-feasible** — implemented as
  `runtime.RefreshTokenSecretResolver` (FX-RUNTIME-006), the durable in-repo path.
- **Service account = RS256 JWT signing required** (`grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer`,
  private key from the SA JSON). RSA → **NOT stdlib** → operator-runtime (`google-auth`). SA reads a Doc via
  doc-sharing with the SA email or domain-wide delegation. Source: …/oauth2/service-account.
- **Scope verification** (sensitive/restricted: `documents.readonly`/`drive.readonly`/`drive.file`) is required
  only for apps **distributed to other users** on consumer data; a **Testing**-status OAuth client (own/test
  users) needs none (user cap + ~7-day refresh-token lifetime per Google's OAuth verification FAQ). Source:
  …/oauth2/production-readiness/restricted-scope-verification + support.google.com/cloud/answer/9110914.

