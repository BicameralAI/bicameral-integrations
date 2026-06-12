<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# OpenAI Admin — backend setup

OpenAI organization audit-log events as governed evidence with actor identity dropped (event type + project + time; actor email/id/IP never read).

- **id** `openai_admin` · **version** 0.1.0 · **channel** beta · **category** security/compliance-evidence · **trust tier** T1
- **status** live-ready · **available** True · **modes** active

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `openai_admin` — Admin API key (api_key, required)
- Wire format: `Authorization: Bearer <admin key>`
- Serves run mode(s): `active`
- Supply via config key `openai_admin` **or** env `BICAMERAL_OPENAI_ADMIN` (env wins when set).
- Where to get it: https://platform.openai.com/docs/api-reference/audit-logs
  - An Org Owner provisions an Admin API key and enables org logging in Data Controls (irreversible).
  - Bicameral sends it as Authorization: Bearer on GET /v1/organization/audit_logs (verified 2026-06-13).

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "openai_admin": {
      "enabled": true,
      "secrets": {
        "openai_admin": "<Admin API key>"
      },
      "runtime": {
        "base_url": "https://api.openai.com"
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `base_url` | False | https://api.openai.com | Host the poll client pins to (anti-SSRF). |

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run openai_admin                 # fetch -> print screened emissions
python -m runtime.cli run-mods openai_admin --mods dependency_risk
python -m runtime.cli run openai_admin --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: audit_event
- PII posture: The EVENT (type + project + UTC time) is the evidence; the actor is structured identity (actor.*.user.email, actor.session.ip_address, user ids) and is DROPPED AT PARSE -- NEVER read. FX-SEC-001 screens secret/PHI/PAN only (NOT generic email/IP) and redact() has no IPv4 scrub, so the parse-time identity drop is the SOLE control for actor identity. Only the non-PII actor.type (session/api_key, allowlisted) is surfaced; the synthesized excerpt is redact()-ed defensively. FX-SEC-001 hard-screens secret/PHI/PAN as the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + identity-drop + defensive redact are built and harness-proven; actor email/id/IP are never read. Gated on operator review + wiring the live audit-log poll (host-pinned to api.openai.com, Bearer Admin key, org logging enabled) to a GatewaySink. To flip: provision the Admin key + enable org logging; wire the runtime poll; run a real poll; review before promoting.

- Gate: Audit-logs API re-verified live 2026-06-13 (platform.openai.com/docs/api-reference/audit-logs): GET /v1/organization/audit_logs, Authorization: Bearer Admin key; each event {id, type, effective_at, project, actor, <detail>}. MATCHES parse_audit_log; the connector reads only the non-PII type/project/actor.type/effective_at.
- Gate: PII: actor identity (email/id/IP) DROPPED at parse (never read) -- the SOLE control, since FX-SEC-001 does not screen generic email/IP and redact() has no IPv4 scrub. Only the non-PII actor.type is surfaced; excerpt redact()-ed defensively. FX-SEC-001 backstops secret/PHI/PAN.
- Gate: The live REST poll + Bearer Admin-key resolution are operator-runtime; org logging must be enabled in Data Controls (irreversible). No live network this cycle. Live flip gated on operator review + a real audit-log poll with an Admin key (ADR-0012).

## References

- audit-logs-api: https://platform.openai.com/docs/api-reference/audit-logs
- administration: https://platform.openai.com/docs/api-reference/administration
- auth: connectors/openai_admin/auth.md
