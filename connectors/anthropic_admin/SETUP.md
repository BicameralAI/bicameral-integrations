<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Anthropic Admin — backend setup

Anthropic organization usage/cost metrics as PII-free aggregate governed evidence (token totals + models; opaque workspace/key ids never surfaced).

- **id** `anthropic_admin` · **version** 0.1.0 · **channel** beta · **category** developer-AI / usage · **trust tier** T1
- **status** live-ready · **available** True · **modes** active

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `anthropic_admin` — Admin API key (sk-ant-admin…) (api_key, required)
- Wire format: `x-api-key: <admin key> (+ anthropic-version: 2023-06-01)`
- Serves run mode(s): `active`
- Supply via config key `anthropic_admin` **or** env `BICAMERAL_ANTHROPIC_ADMIN` (env wins when set).
- Where to get it: https://docs.anthropic.com/en/api/administration-api
  - An organization admin provisions an Admin API key (sk-ant-admin…) in the Claude Console (Admin role required).
  - Bicameral sends it as x-api-key (with anthropic-version: 2023-06-01) on GET /v1/organizations/usage_report/messages (verified 2026-06-13). Distinct from a standard API key.

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "anthropic_admin": {
      "enabled": true,
      "secrets": {
        "anthropic_admin": "<Admin API key (sk-ant-admin\u2026)>"
      },
      "runtime": {
        "base_url": "https://api.anthropic.com",
        "bucket_width": "1d"
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `base_url` | False | https://api.anthropic.com | Host the poll client pins to (anti-SSRF). |
| `bucket_width` | False | 1d | Time-bucket granularity (1m / 1h / 1d). Operator-runtime poll knob; poll <= once/min. |

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run anthropic_admin                 # fetch -> print screened emissions
python -m runtime.cli run-mods anthropic_admin --mods dependency_risk
python -m runtime.cli run anthropic_admin --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: usage_metrics
- PII posture: PII-FREE aggregate by construction. parse_usage synthesizes its OWN excerpt from numeric token totals (input = uncached + cache_read + nested cache_creation.ephemeral_*; + output) and distinct model names. The opaque workspace_id / api_key_id grouping dimensions are NEVER surfaced; there is no user email/name in the usage surface; no author field. No provider free text is emitted, so no redaction is required (the copilot/cursor PII-free-by-construction class). FX-SEC-001 hard-screens secret/PHI/PAN as the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse is built and harness-proven; the usage surface is PII-free aggregate (token totals + models). Gated on operator review + wiring the live usage poll (host-pinned to api.anthropic.com, Admin key) to a GatewaySink. To flip: provision the Admin API key; wire the runtime poll; run a real usage poll; review before promoting.

- Gate: Usage API re-verified live 2026-06-13 (docs.anthropic.com/en/api/usage-cost-api): GET /v1/organizations/usage_report/messages, x-api-key Admin key (sk-ant-admin…) + anthropic-version; response uncached_input_tokens + cache_creation (NESTED ephemeral_1h/5m) + cache_read_input_tokens + output_tokens by model/workspace/service_tier. MATCHES parse_usage incl. the nested cache_creation summation.
- Gate: PII: PII-free aggregate by construction — synthesized token-totals excerpt; opaque workspace_id/api_key_id never surfaced; no author; no provider free text. FX-SEC-001 backstops secret/PHI/PAN.
- Gate: The live REST poll + Admin-key resolution are operator-runtime; no live network this cycle. Live flip gated on operator review + a real usage poll with an Admin key (ADR-0012). Per-user cost (Claude Code Analytics API) is deferred behind the redaction model (per-user PII).

## References

- admin-api: https://docs.anthropic.com/en/api/administration-api
- usage-cost-api: https://docs.anthropic.com/en/api/usage-cost-api
- auth: connectors/anthropic_admin/auth.md
