<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Google Drive (Docs) — backend setup

Google Docs documents fetched by id (documents.get) as governed evidence.

- **id** `google_drive` · **version** 0.1.0 · **channel** beta · **category** docs · **trust tier** T1/T3
- **status** live-ready · **available** True · **modes** active

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `google_drive` — Google OAuth access token (oauth2, required)
- Wire format: `Authorization: Bearer <access_token>`
- Serves run mode(s): `active`
- OAuth scopes: `https://www.googleapis.com/auth/documents.readonly`, `https://www.googleapis.com/auth/drive.readonly`
- Refresh owner: **operator** (token exchange/refresh needs operator oversight)
- Supply via config key `google_drive` **or** env `BICAMERAL_GOOGLE_DRIVE` (env wins when set).
- Where to get it: https://developers.google.com/identity/protocols/oauth2
  - An access token is SHORT-LIVED (~1 hour; honor the returned expires_in) — pasting one is a quick test, not a durable setup.
  - Durable option A (user OAuth): register an OAuth client (Testing publishing status = NO verification for your own/test users), grant the documents.readonly / drive.readonly scopes, and persist the REFRESH token + client id/secret. The stdlib runtime.RefreshTokenSecretResolver mints fresh access tokens from these (plain POST, no RSA).
  - Durable option B (server, service account): use a service-account JSON; share the doc with the SA email (or use domain-wide delegation to impersonate). This needs RS256 JWT signing (google-auth) and is OPERATOR-RUNTIME — NOT stdlib.
  - Quick test token: the OAuth 2.0 Playground (developers.google.com/oauthplayground) issues a ~1h access token for the selected scopes. Restricted-scope verification only applies to apps DISTRIBUTED to other users.

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "google_drive": {
      "enabled": true,
      "secrets": {
        "google_drive": "<Google OAuth access token>"
      },
      "runtime": {
        "document_id": "<Document ID>"
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `document_id` | True | — | The Google Doc id to fetch (validated [A-Za-z0-9_-]{1,200}; spliced into GET /v1/documents/{id}). |

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run google_drive --document-id <a Google Doc id>                 # fetch -> print screened emissions
python -m runtime.cli run-mods google_drive --mods dependency_risk
python -m runtime.cli run google_drive --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: document
- PII posture: Document title + flattened body text (untrusted, possibly PII-dense). FX-SEC-001 producer screen rejects secret/PHI/PAN before emit.

## Go-live

Readiness: Flip-ready, NOT yet Live. Code-ready (FX-GDRIVE-002, documents.get) and harness-proven against a reference sink — but still incomplete: the Live flip is gated on operator human review + a live test against the real Google Docs API with a real OAuth credential. To flip: provide a durable credential (refresh token via RefreshTokenSecretResolver, or a service-account JSON at the operator runtime) + a document id; wire GatewaySink; run the live test; review before promoting to Live.

- Gate: Bearer-header assumption + multi-tab docs confirmed against a live response before the Live flip. Multi-tab docs (content under tabs[].documentTab.body) emit title-only — extract_document_text walks the legacy body; includeTabsContent/tabs[] deferred.
- Gate: OAuth token refresh is now stdlib (runtime.RefreshTokenSecretResolver, FX-RUNTIME-006) — pasting a raw access token is a ~1h TEST only; the durable path is the refresh resolver (user OAuth) or a service-account JSON (operator-runtime, RS256/google-auth, not stdlib). Folder polling (Drive files.list) + push-notification webhooks remain deferred.
- Gate: Live flip GATED on human review + live testing: code-complete and harness-proven through runtime/ against a reference sink, but UNVERIFIED against the live Google Docs API with a real OAuth credential — no machine has minted a real token and fetched a real document yet. The operator must run the live test (durable path = the refresh resolver) and review the result before promoting; until then this connector is flip-ready, NOT Live (ADR-0012).

## References

- api: https://developers.google.com/docs/api/reference/rest/v1/documents/get
- auth: https://developers.google.com/identity/protocols/oauth2
- drive-api: https://developers.google.com/drive/api/guides/about-sdk
