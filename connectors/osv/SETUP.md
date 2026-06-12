<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# OSV — backend setup

OSV.dev open-source vulnerability records as redact-and-pass governed evidence (free unauthenticated query API; public technical vuln data).

- **id** `osv` · **category** security/compliance-evidence · **trust tier** T1
- **status** live-ready · **available** True · **modes** active

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "osv": {
      "enabled": true,
      "secrets": {},
      "runtime": {
        "query": "<Query scope (package / ecosystem / commit)>",
        "base_url": "https://api.osv.dev"
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `query` | True | — | What the operator runtime queries OSV.dev for — e.g. a package + ecosystem, a commit, or a purl. The live query client (POST /v1/query, /v1/querybatch, GET /v1/vulns/{id}) is operator-runtime. |
| `base_url` | False | https://api.osv.dev | Host the query client pins to (anti-SSRF). Default is the public OSV.dev API. |

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run osv                 # fetch -> print screened emissions
python -m runtime.cli run-mods osv --mods dependency_risk
python -m runtime.cli run osv --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: vulnerability
- PII posture: OSV records are PUBLIC technical vulnerability data (CVE/GHSA ids, package names, severity scores). The free-text summary + details are redact-and-passed (secret/PHI/PAN + email/phone scrubbed) for parity -- a description can embed a contributor email or a tokened URL, and redaction is non-destructive. The opaque vuln id floor is NOT redacted; severity/packages/aliases metadata is technical. No person attribution (no author field). FX-SEC-001 hard-screens secret/PHI/PAN as the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + redact-and-pass are built and harness-proven; summary/details redact-and-passed, opaque vuln id floor. No credentials (free unauthenticated API). Gated on operator review + wiring the live query client (host-pinned to api.osv.dev) to a GatewaySink. To flip: set the query scope; wire the runtime query client; run a real query; review before promoting.

- Gate: OSV schema re-verified live 2026-06-13 (ossf.github.io/osv-schema): id+modified required, all else optional; summary/details free-text, severity[{type,score}], affected[].package.name, references[].url, aliases[] -- every field parse_vuln reads MATCHES. No drift.
- Gate: PII: summary + details redact-and-passed (secret/PHI/PAN + email/phone); opaque vuln id floor un-redacted; technical metadata kept; no author. OSV is public data. FX-SEC-001 backstops secret/PHI/PAN.
- Gate: The live OSV.dev query client (POST /v1/query, /v1/querybatch, GET /v1/vulns/{id}) is operator-runtime; no live network this cycle. Live flip gated on operator review + a real query against the public API (ADR-0012).

## References

- api: https://google.github.io/osv.dev/api/
- schema: https://ossf.github.io/osv-schema/
- auth: connectors/osv/auth.md
