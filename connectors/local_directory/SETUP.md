<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Local Directory — backend setup

Files dropped in a watched local directory as redact-and-pass governed evidence (no network credentials; host filesystem permissions are the access control).

- **id** `local_directory` · **version** 0.1.0 · **channel** beta · **category** file/static-import · **trust tier** T0
- **status** live-ready · **available** True · **modes** passive

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "local_directory": {
      "enabled": true,
      "secrets": {},
      "runtime": {
        "directory": "<Watched directory path>",
        "extensions": [
          ".md",
          ".txt",
          ".json"
        ],
        "max_bytes": 1048576
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `directory` | True | — | Absolute path the operator runtime scans (non-recursive iterdir; hidden files and subdirectories ignored). Files become evidence — scope it to a directory whose contents you intend to govern. |
| `extensions` | False | ['.md', '.txt', '.json'] | Only files with these extensions are ingested. Operator-runtime filter. |
| `max_bytes` | False | 1048576 | Files larger than this are skipped, not ingested (default 1 MiB). Operator-runtime guard. |

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run local_directory                 # fetch -> print screened emissions
python -m runtime.cli run-mods local_directory --mods dependency_risk
python -m runtime.cli run local_directory --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: planning
- PII posture: File content and the filename stem are operator-supplied free text -> redact-and-passed (secret/PHI/PAN + email/phone scrubbed to placeholders; SG-2026-06-13-A — a local/passive source still needs redaction parity, since no network boundary is not no PII boundary). The file path is sha256-tokenized into an opaque ref so the operator's filesystem layout never enters the ledger. FX-SEC-001 hard-screens secret/PHI/PAN as the un-bypassable backstop. The operator additionally owns directory scoping, the extension allow-list, and the size cap.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + redact-and-pass + opaque path tokenization are built and harness-proven. No network credentials exist (host filesystem permissions). Gated on operator review + wiring the live directory scan (with the extension allow-list, size cap, and watermark two-phase commit) to a GatewaySink. To flip: set the watched directory path; wire the runtime scan; drop a test file; review before promoting.

- Gate: No external provider contract — local filesystem source; nothing to re-verify against a vendor API. Parse shape {path, content, modified, source_type_label} ported from bicameral-mcp events/sources/local_directory.py.
- Gate: PII: file content + filename stem redact-and-passed (secret/PHI/PAN + email/phone); path sha256-tokenized into an opaque ref (no FS-layout leak). FX-SEC-001 backstops secret/PHI/PAN.
- Gate: Live directory scan, non-recursive iterdir, extension allow-list, 1 MiB size cap, and watermark two-phase commit are operator-runtime; no live ingest this cycle. Live flip gated on operator review + a real watched-directory scan (ADR-0012).

## References

- auth: connectors/local_directory/auth.md
- contract: connectors/local_directory/references.md
