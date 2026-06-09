<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Google Drive (Docs) — backend setup

Google Docs documents fetched by id (documents.get) as governed evidence.

- **id** `google_drive` · **category** docs · **trust tier** T1/T3
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
  - Register an OAuth client and grant consent for the documents.readonly / drive.readonly scopes.
  - The mcp UI owns the consent UX; the operator runtime stores the access token and OWNS refresh (the SecretResolver returns a valid token).

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

Readiness: Code-ready (FX-GDRIVE-002, documents.get). Operator provides a valid OAuth access token (refresh operator-owned) + a document id; then wires GatewaySink.

- Gate: Bearer-header assumption + multi-tab docs confirmed against a live response before the Live flip. Multi-tab docs (content under tabs[].documentTab.body) emit title-only — extract_document_text walks the legacy body; includeTabsContent/tabs[] deferred.
- Gate: OAuth token refresh + folder polling (Drive files.list) + push-notification webhooks are operator-runtime / deferred.

## References

- api: https://developers.google.com/docs/api/reference/rest/v1/documents/get
- auth: https://developers.google.com/identity/protocols/oauth2
- drive-api: https://developers.google.com/drive/api/guides/about-sdk
