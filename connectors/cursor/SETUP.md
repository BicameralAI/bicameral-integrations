<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Cursor — backend setup

Cursor team daily-usage metrics (Admin API) as PII-free, governed evidence.

- **id** `cursor` · **version** 0.1.0 · **channel** beta · **category** developer-ai · **trust tier** T1
- **status** live-ready · **available** True · **modes** active

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `cursor` — Team Admin API key (basic, required)
- Wire format: `Authorization: Basic (API key as username, empty password)`
- Serves run mode(s): `active`
- Supply via config key `cursor` **or** env `BICAMERAL_CURSOR` (env wins when set).
- Where to get it: https://cursor.com/docs/account/teams/admin-api
  - A team administrator mints an Admin API key in the Cursor dashboard (team settings).
  - The key is sent as HTTP Basic with the key as the username and an empty password.

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "cursor": {
      "enabled": true,
      "secrets": {
        "cursor": "<Team Admin API key>"
      },
      "runtime": {
        "base_url": "https://api.cursor.com/teams/daily-usage-data",
        "body": "<Date-range request body>"
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `base_url` | False | https://api.cursor.com/teams/daily-usage-data | The Cursor Admin API daily-usage endpoint (host pinned api.cursor.com; verified 2026-06-11). |
| `body` | True | — | POST body {startDate, endDate} in epoch MILLISECONDS, range <= 30 days. page/pageSize (body) paginate; the reference client fetches one page (widen pageSize for teams > one page). |

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run cursor                 # fetch -> print screened emissions
python -m runtime.cli run-mods cursor --mods dependency_risk
python -m runtime.cli run cursor --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: usage_metrics
- PII posture: PII-free by construction: parse-time allowlist reads only numeric metrics + mostUsedModel + the OPAQUE integer userId; email/name/clientVersion are NEVER read (FX-SEC-001 does not detect a generic email, so the control is the allowlist, not a downstream screen). Free-text day/model pass through redact().

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse surface (PII-free allowlist) + the live fetch-half (build_cursor_spec) are built and harness-proven against a recorded fixture; contract re-verified live 2026-06-11. Gated on operator human review + a live poll with a real team Admin API key. To flip: provide the key + a date-range body; wire GatewaySink; run the live poll; review before promoting.

- Gate: Contract verified live 2026-06-11: POST https://api.cursor.com/teams/daily-usage-data, HTTP Basic (key as username), body {startDate,endDate} epoch-ms <= 30 days, `data` envelope; rows carry userId/email/metrics, no `name`.
- Gate: Pagination is POST-body `page`/`pageSize` with response `pagination.hasNextPage` (verified 2026-06-11). The reference client (build_cursor_spec) issues a SINGLE request and is NOT yet wired for multi-page — a team larger than one page truncates; widen `pageSize` or wire a body-page pager before relying on full coverage. (runtime/poll_specs.py build_cursor_spec carries stale 'inferred/unverified' comments to reconcile.)
- Gate: PII control is the parse-time allowlist (no downstream screen for generic email) — do NOT relax it. Operator runs the live poll + reviews before promoting to Live (ADR-0012).

## References

- admin-api: https://cursor.com/docs/account/teams/admin-api
