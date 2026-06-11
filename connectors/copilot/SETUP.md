<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# GitHub Copilot — backend setup

GitHub Copilot org metrics (aggregate, PII-free) as governed evidence.

- **id** `copilot` · **category** developer-ai · **trust tier** T1
- **status** live-ready · **available** True · **modes** active

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `copilot` — GitHub token (PAT/OAuth) with read:org (api_key, required)
- Wire format: `Authorization: Bearer <token>`
- Serves run mode(s): `active`
- Supply via config key `copilot` **or** env `BICAMERAL_COPILOT` (env wins when set).
- Where to get it: https://docs.github.com/en/rest/copilot/copilot-metrics
  - Create a PAT (or OAuth app token) with `manage_billing:copilot` OR `read:org` / `read:enterprise`.
  - Sent as Authorization: Bearer (with Accept: application/vnd.github+json + X-GitHub-Api-Version).

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "copilot": {
      "enabled": true,
      "secrets": {
        "copilot": "<GitHub token (PAT/OAuth) with read:org>"
      },
      "runtime": {
        "base_url": "<Copilot metrics endpoint (org-templated)>",
        "api_version": "2022-11-28",
        "per_page": 100
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `base_url` | True | — | GET .../orgs/<org>/copilot/metrics — template YOUR org in (host pinned api.github.com; default carries an ORG placeholder). |
| `api_version` | False | 2022-11-28 | GitHub REST API version header (valid; EOL 2028-03-10). |
| `per_page` | False | 100 | Results per page (max 100; page-number pagination, 100-day lookback). |

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run copilot                 # fetch -> print screened emissions
python -m runtime.cli run-mods copilot --mods dependency_risk
python -m runtime.cli run copilot --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: usage_metrics
- PII posture: PII-free: the aggregate metrics object carries no per-developer identity (one emission per day). The newer per-user NDJSON usage-metrics report is deferred behind a future redaction-and-pass model.

## Go-live

Readiness: Flip-ready, NOT yet Live. Aggregate PII-free parse surface + the live fetch-half (build_copilot_spec) are built and harness-proven against a recorded fixture (contract verified 2026-06-08). Gated on operator review + a live poll with a real token. To flip: provide a read:org token + the org-templated endpoint; wire GatewaySink; run the live poll; review before promoting.

- Gate: Contract verified docs.github.com 2026-06-08: top-level JSON array of day objects (one emission/day); page/per_page pagination (max 100; 100-day lookback) via PageNumberPager (stop-on-short-page). X-GitHub-Api-Version 2022-11-28 is an argument, not baked.
- Gate: Operator templates their org into base_url (required; the default carries an ORG placeholder that will 404).
- Gate: Live flip gated on operator human review + a live poll with a real read:org token (ADR-0012).

## References

- api: https://docs.github.com/en/rest/copilot/copilot-metrics
- auth: https://docs.github.com/en/rest/overview/permissions-required-for-fine-grained-personal-access-tokens
