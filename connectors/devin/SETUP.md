<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Devin — backend setup

Devin agentic-coding sessions (v3 enterprise API) as redacted, governed evidence.

- **id** `devin` · **category** developer-ai · **trust tier** T1
- **status** live-ready · **available** True · **modes** active

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `devin` — Service-User API key (api_key, required)
- Wire format: `Authorization: Bearer <cog_ Service-User key>`
- Serves run mode(s): `active`
- Supply via config key `devin` **or** env `BICAMERAL_DEVIN` (env wins when set).
- Where to get it: https://docs.devin.ai/api-reference/authentication
  - In your Devin organization settings, create a Service-User API key (cog_ prefix). It is shown once at creation and is RBAC-scoped; a Personal Access Token works too where available.
  - Copy the key — it is sent as an Authorization: Bearer header. Devin publishes no webhooks, so this is the only credential (active poll only).

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "devin": {
      "enabled": true,
      "secrets": {
        "devin": "<Service-User API key>"
      },
      "runtime": {
        "base_url": "<Sessions endpoint base URL>"
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `base_url` | True | — | The v3 sessions list endpoint with your org templated in: https://api.devin.ai/v3/organizations/<org_id>/sessions (host pinned api.devin.ai; org_id goes in the path). Consumed by runtime build_devin_spec(base_url=...); there is no default (the operator supplies org_id). |

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run devin                 # fetch -> print screened emissions
python -m runtime.cli run-mods devin --mods dependency_risk
python -m runtime.cli run devin --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: session
- PII posture: Session free-text (title, structured_output, message trail) may carry secrets/PII, so it is passed through adapter.core.redaction.redact (redact-and-pass) before emit; the first pull_requests[].pr_url is kept un-redacted as the artifact location (github/gitlab/jira precedent). FX-SEC-001 producer screen is the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + redaction surface and the live fetch-half (build_devin_spec, runner-wired) are code-complete and harness-proven against a reference sink — but still incomplete: the Live flip is gated on operator human review + a live poll against the real Devin v3 enterprise API with a real Service-User (cog_) key. To flip: provide the api key + the org-templated base_url; wire GatewaySink; run the live poll; review before promoting to Live.

- Gate: The operator templates org_id into the REQUIRED base_url (https://api.devin.ai/v3/organizations/<org_id>/sessions); build_devin_spec has no default base_url, so a missing value fails closed (ConfigError) before any request.
- Gate: v3 contract (items envelope; pull_requests[] of {pr_url, pr_state}; cursor end_cursor/has_next_page re-sent as ?after=; Bearer cog_ Service-User key) was doc-verified 2026-06-08 and re-verified live 2026-06-11 (docs.devinenterprise.com) — but UNVERIFIED against the live API with a real cog_ key. The operator must run the live poll and review the result before promoting to Live (ADR-0012).
- Gate: This connector targets the v3 ENTERPRISE API (docs.devinenterprise.com). The parallel v1 API (docs.devin.ai: GET /v1/sessions, `sessions` envelope, singular `pull_request`, limit/offset, apk_ keys) is the 2026-06-08-corrected drift shape — do NOT cite or wire it (SG-2026-06-11-A).

## References

- api: https://docs.devin.ai/api-reference/overview
- auth: https://docs.devin.ai/api-reference/authentication
- sessions-v3: https://docs.devinenterprise.com/api-reference/v3/sessions/organizations-sessions
