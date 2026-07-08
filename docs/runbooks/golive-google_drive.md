# Go-Live Runbook — Google Drive (Docs)

**Status:** flip-ready, NOT yet Live · **Mode:** active `documents.get` · **Trust:** T1/T3
**Descriptor:** `connectors/google_drive/config.json` · **Backend:** `connectors/google_drive/SETUP.md` · **Auth facts:** `connectors/google_drive/auth.md`

Fetches a single Google Doc by id (`GET https://docs.googleapis.com/v1/documents/{id}`) and emits its flattened body as governed evidence. Folder polling (Drive `files.list`) and push-notification webhooks are deferred.

## Credentials

| Key | What | Where to get it | Notes |
|---|---|---|---|
| `google_drive` | OAuth access token (Bearer) | see options below | short-lived (~1h) |

Token options (in order of durability):
- **Durable (recommended):** user-OAuth **refresh token** + client id/secret → the stdlib `runtime.RefreshTokenSecretResolver` (FX-RUNTIME-006) mints fresh access tokens (plain POST, no RSA). Scopes: `documents.readonly` + `drive.readonly`.
- **Durable (server):** a service-account JSON (RS256 JWT, `google-auth`) — operator-runtime, NOT stdlib; share the doc with the SA email.
- **Quick test only:** an OAuth Playground access token (~1h) — fine for a one-shot live test, not durable.

## Live-flip steps

0. **Guided setup (recommended, #227):** `python -m runtime.cli configure google_drive` runs the
   OAuth consent flow in your browser (PKCE + loopback catcher on 127.0.0.1) and persists the
   **durable refresh triple** (`google_drive_refresh_token`/`_client_id`/`_client_secret`) — the
   run path then mints access tokens automatically (`cli.build_resolver` → FX-RUNTIME-006), so
   step 4's manual wiring is no longer needed. It also prompts the `document_id` and runs the
   verify fetch. `--paste-token` instead stores a raw ~1h access token (test only, NOT durable).
   Steps 1 + 4 below are the manual equivalent.
1. **Place the credential + doc id:**
   ```json
   {
     "connectors": { "google_drive": {
       "enabled": true,
       "secrets": { "google_drive": "<OAuth access token>" },
       "runtime": { "document_id": "<a Google Doc id>" }
     }},
     "gateway": { "endpoint": "https://<your-bot>/api/v1/ingest", "token": "<ingest token>" }
   }
   ```
   (or `BICAMERAL_GOOGLE_DRIVE`). The doc id can also be passed as `--document-id <id>`.
2. **Dry-run (local sink):** `python -m runtime.cli run google_drive --document-id <id>` → prints the screened document emission. Confirm the title + flattened text look right and no secret/PII is printed.
3. **Live test:** `python -m runtime.cli run google_drive --document-id <id> --sink gateway` → expect 201.
4. **Durable wiring:** for ongoing use, wire the `RefreshTokenSecretResolver` (refresh token + client id/secret) so access tokens auto-refresh; a pasted access token expires in ~1h.

## Wire gates to confirm against the live response

- **Bearer header** + the `documents.get` Document shape (`documentId` / `title` / `body`) match live.
- **Multi-tab docs**: content under `tabs[].documentTab.body` emits **title-only** today (the walker reads the legacy `body`; `includeTabsContent`/`tabs[]` deferred) — confirm your target doc's body is on the legacy surface, or accept title-only for multi-tab docs.
- `documentId` is **fullmatch-guarded** (`[A-Za-z0-9_-]{25,128}`) before becoming the wire ref (hardened).

## Promote / rollback

- **Promote to Live** when a real document fetch returns the expected title/text at 201, on a durable credential (refresh resolver or SA JSON). Operator decision.
- **Rollback:** remove `gateway.endpoint` or `enabled: false`; revoke the OAuth grant / rotate the SA key.

## Security notes for the live test (purple-team #133)

Document title + body are untrusted/possibly PII-dense → FX-SEC-001 hard screen rejects secret/PHI/PAN before emit. Body-walk is type-confusion-guarded (a hostile 200 shape yields empty text, never a crash). Redirects not followed; the single GET is not paginated (the 8 MiB body cap applies). Residual accepted-risk: within-field `order_id: <PAN>` suppression (see runbooks README).
