# Connector backend setup — the general how-to

How to stand up the **backend** for any connector (and run mods) **without the mcp UI**. Per-connector
specifics live in each `connectors/<id>/SETUP.md` (generated from that connector's `config.json`); this
doc explains the mechanics those runbooks assume. The UI is optional — this is the headless path.

## 1. The config model

Operator config lives in **`config/bicameral.local.json`** — a **gitignored** file (the glob block in
`.gitignore` also covers `*.local.json` / `secrets*.json`, so a renamed copy can't slip in). Copy the
committed template and fill real values:

```bash
cp config/bicameral.example.json config/bicameral.local.json
$EDITOR config/bicameral.local.json   # NEVER commit this file
```

Shape (per connector's `SETUP.md` gives its exact keys):

```json
{
  "connectors": {
    "linear": {
      "enabled": true,
      "secrets": { "linear": "…", "linear_webhook": "…" },
      "runtime": { "page_size": 50 }
    }
  },
  "mods": { "dependency_risk": { "enabled": true } },
  "gateway": { "endpoint": "", "token": "" }
}
```

Keys prefixed with `_` are treated as comments.

## 2. Secrets — file or env (env wins)

Each credential resolves by its **key** (declared in the connector's `config.json` → shown in its
`SETUP.md`). Two sources, env taking precedence:

- **Env (recommended for prod/CI — no secret on disk):** `BICAMERAL_<KEY>` (the key, uppercased). A
  credential keyed `linear_webhook` → `BICAMERAL_LINEAR_WEBHOOK`. A set, non-empty env var **wins over the
  file**; a set-but-empty one falls through to the file.
- **File:** the `secrets` block above.

The resolver never logs or echoes a value. **Never commit secrets** — the gitignore + a CI secret-shape
scan over tracked `config/*.json` enforce it; protect your local file's permissions and don't sync it.

## 3. Run it

```bash
python -m runtime.cli list                          # configured connectors/mods + which are runnable
python -m runtime.cli run <connector>               # active fetch -> print screened emissions
python -m runtime.cli run google_drive --document-id <id>
python -m runtime.cli run-mods <connector> --mods dependency_risk
python -m runtime.cli run <connector> --sink gateway   # real POST to the bot (go-live)
```

The default sink is **local** — it prints screened emissions (`source_id`/`title`/`excerpt`, never a
secret). `--limit N` caps what's printed. Only `--sink gateway` egresses.

## 4. Webhooks (webhook connectors)

A webhook connector's **signing secret** is for the *receive* path (verifying inbound deliveries), which
the operator runtime serves — it is **NOT** used by `runtime.cli run` (that's the active fetch). To wire
webhooks: provision an inbound **receiver URL** (your runtime's endpoint), register it at the provider,
and store the provider's signing secret under the connector's `webhook_secret` key. The connector verifies
the signature + replay window on each delivery.

## 5. OAuth (OAuth connectors, e.g. Google Drive)

OAuth credentials carry `refresh_owner: operator`. The **UI owns the consent UX**; the CLI only sets
`Authorization: Bearer <token>` and does not perform the OAuth dance. A Google **access token is
short-lived (~1 hour** — the response carries `expires_in`), so a pasted token is a **test, not a setup**.
The *durable* credential is the **refresh token** (user OAuth) or a **service-account JSON** (server).
Three ways to supply auth:

- **Quick test** — paste a ~1 h access token (OAuth 2.0 Playground or your app) as the connector's secret /
  `BICAMERAL_<KEY>`. It 401s after ~1 hour.
- **Durable, stdlib (recommended for user OAuth)** — `runtime.RefreshTokenSecretResolver` (FX-RUNTIME-006):
  give it the **refresh token + client id/secret**, and it mints a fresh access token on each `resolve`,
  caching until `expires_in`. The refresh grant is a **plain form POST (no RSA)**, so it's stdlib-only.
  Construct it in your operator runtime in place of `FileSecretResolver` (it delegates other keys to a base
  resolver). An OAuth client in **Testing** publishing status needs **no Google verification** for your own
  / test-user accounts.
- **Durable, server (service account)** — a service-account JSON; share the doc with the SA email (or use
  domain-wide delegation to impersonate a user). Minting a token here requires **RS256 JWT signing**, which
  needs `google-auth` / `cryptography` — it is **operator-runtime, NOT stdlib** (this repo does not ship a
  stdlib service-account resolver). Your operator runtime supplies that `SecretResolver`.

Restricted-scope **verification** (and a security assessment) is required only for apps **distributed to
other users** on consumer data — not for your own account / a service account on your own data.

## 6. Go-live (real emission)

`--sink gateway` POSTs to the bot. It is **default-gated**: with no `gateway.endpoint` configured it
raises `GatewayEmissionGated` (safe by default). Set `gateway.endpoint` + `gateway.token`, clear the
connector's `wire_gates` (the pre-Live checklist in its `SETUP.md`), then run with `--sink gateway`.
Every emission is FX-SEC-001-screened before any sink.

## 7. Troubleshooting (the real error strings)

| Error | Meaning / fix |
|---|---|
| `error: <connector>: missing required credential(s): […]` | A required credential is unresolved — set it in the file or `BICAMERAL_<KEY>`. |
| `secret_unresolved:<source_id>` | The fetch found no secret for that source — same fix. |
| `bad_document_id` | The Google Doc id failed the `[A-Za-z0-9_-]{1,200}` guard — pass a clean `--document-id`. |
| `GatewayEmissionGated` | `--sink gateway` with no `gateway.endpoint` — configure it (intentional default-safe gate). |
| `error: <connector>: secret(s) under unknown credential key(s): […]` | A typo'd secret key — match the keys in the connector's `SETUP.md`. |
| `unknown or not-runnable connector` | The connector has no active runner (e.g. webhook-receive-only). |

## 8. Security posture (summary)

Secrets never committed (gitignore glob + shape scan) and never printed (the CLI prints only screened
emissions; errors name credential **keys**, never values). Plaintext-secret-on-disk in the gitignored file
is the accepted posture — protect file permissions; prefer env vars where you won't put secrets on disk.
See [ADR-0016](adr/0016-operator-local-config-and-runner.md).
