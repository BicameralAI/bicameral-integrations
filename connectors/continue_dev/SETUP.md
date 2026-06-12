<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Continue — backend setup

Continue (continue.dev) developer-AI dev-data events (local JSONL) as redact-and-pass governed evidence (prompt/completion text scrubbed; opaque userId).

- **id** `continue_dev` · **category** developer-AI / source-control · **trust tier** T0
- **status** live-ready · **available** True · **modes** passive

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "continue_dev": {
      "enabled": true,
      "secrets": {},
      "runtime": {
        "dev_data_path": "<Continue dev-data JSONL path>",
        "no_code_lever": false
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `dev_data_path` | True | — | Path (or glob) to Continue's local development-data JSONL the operator runtime ingests (one event per developer-AI interaction). File import only; no network, no credential. |
| `no_code_lever` | False | False | When the operator sets Continue's level:noCode, Continue strips prompt/completion text fields AT SOURCE before they are written — defense-in-depth on top of Bicameral's redact-and-pass. |

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run continue_dev                 # fetch -> print screened emissions
python -m runtime.cli run-mods continue_dev --mods dependency_risk
python -m runtime.cli run continue_dev --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: development_data
- PII posture: Continue dev-data events carry developer-AI interaction text (prompt/completion/content/message) that can contain code with secrets/emails -> redact-and-passed (secret/PHI/PAN + email/phone scrubbed; SG-2026-06-13-A). The userId author is redact-and-passed too (an opaque id passes unchanged; an email-shaped userId is scrubbed); the 'continue {eventName}' floor + the technical metadata (name/schema/model) are not redacted. The operator's Continue level:noCode lever additionally strips text fields AT SOURCE. FX-SEC-001 hard-screens secret/PHI/PAN as the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + redact-and-pass are built and harness-proven; prompt/completion text + userId redact-and-passed, the operator level:noCode lever strips at source. No credentials (local file import). Gated on operator review + wiring the live JSONL file-watch / HTTP-sink to a GatewaySink. To flip: set the dev-data path; wire the runtime ingest; ingest a real event; review before promoting.

- Gate: Dev-data shape re-confirmed live 2026-06-13 (docs.continue.dev development-data): schema-versioned event JSON blob + HTTP-sink. Field detail (eventName base field, no event-id, prompt/completion/content/message text fields, level:noCode lever) pinned 2026-06-08 against docs/source and handled defensively (eventName/name fallback, schema-version-tolerant, str-coerced); the doc defers the field list to source (SG-2026-06-13-D). No drift on the confirmed surface.
- Gate: PII: prompt/completion/content/message excerpt + userId author redact-and-passed (secret/PHI/PAN + email/phone); event-kind floor + technical metadata kept; operator level:noCode strips text at source. FX-SEC-001 backstops secret/PHI/PAN.
- Gate: The live JSONL file-watch / HTTP-sink collection is operator-runtime; no live ingest this cycle. Live flip gated on operator review + a real dev-data ingest (ADR-0012).

## References

- dev-data: https://docs.continue.dev/customize/deep-dives/development-data
- repo: https://github.com/continuedev/continue
- auth: connectors/continue_dev/auth.md
