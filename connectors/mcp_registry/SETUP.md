<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# MCP Registry — backend setup

Public MCP Registry server entries as PII-free, no-auth governed evidence.

- **id** `mcp_registry` · **category** agent-ecosystem · **trust tier** T1
- **status** live-ready · **available** True · **modes** active

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "mcp_registry": {
      "enabled": true,
      "secrets": {},
      "runtime": {
        "base_url": "https://registry.modelcontextprotocol.io/v0/servers"
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `base_url` | False | https://registry.modelcontextprotocol.io/v0/servers | Public, no-auth GET /v0/servers list (verified 2026-06-08). Cursor pagination via metadata.nextCursor. |

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run mcp_registry                 # fetch -> print screened emissions
python -m runtime.cli run-mods mcp_registry --mods dependency_risk
python -m runtime.cli run mcp_registry --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: mcp_server
- PII posture: Public registry metadata only (server name/title/description, repository/website URL, version). PII-free; no credential; no per-person data.

## Go-live

Readiness: Flip-ready, NOT yet Live. Public no-auth parse + live fetch-half (build_mcp_registry_spec) built, harness-proven, and runner-wired this cycle. No secret to provision. To flip: configure the gateway endpoint; run the public poll; review before promoting to Live.

- Gate: Verified contract (registry.modelcontextprotocol.io/openapi.yaml 2026-06-08): public no-auth GET /v0/servers; list under `servers`; each entry nests the server under `server`; cursor pagination via response `metadata.nextCursor` (no has-more — stop on absent).
- Gate: No credential (public). Live flip is gated only on the operator wiring GatewaySink + running the public poll + review (ADR-0012).

## References

- openapi: https://registry.modelcontextprotocol.io/openapi.yaml
- reference: https://github.com/modelcontextprotocol/registry
