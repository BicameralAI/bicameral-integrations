<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# SARIF — backend setup

SARIF 2.1.0 static-analysis findings (file import) as redact-and-pass governed evidence — a secret-scanner finding's message is scrubbed but preserved, not dropped.

- **id** `sarif` · **version** 0.1.0 · **channel** beta · **category** security/compliance-evidence · **trust tier** T0
- **status** live-ready · **available** True · **modes** passive

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "sarif": {
      "enabled": true,
      "secrets": {},
      "runtime": {
        "report_path": "<SARIF file / CI-artifact glob>"
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `report_path` | True | — | Path (or glob) to the SARIF 2.1.0 report(s) the operator runtime ingests — e.g. a CI scan artifact. File import only; no network, no credential. |

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run sarif                 # fetch -> print screened emissions
python -m runtime.cli run-mods sarif --mods dependency_risk
python -m runtime.cli run sarif --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: finding
- PII posture: The SARIF schema carries no user PII by design, but a SECURITY-SCANNER finding's message.text can quote the very secret it flags (a secret-scanner emits 'Detected AWS key AKIA... in config.py'). So message.text is redact-and-passed -- redact() scrubs the CATALOG secret formats (AWS, classic + fine-grained GitHub, Azure, PEM, JWT, Slack, Google API key, Stripe live, GitLab, npm, OpenAI -- broadened by purple-team #185 / SG-2026-06-13-F) + PHI/PAN + email/phone. This is the security-correct choice (SG-2026-06-13-E): emitted RAW, FX-SEC-001 would HARD-REJECT a catalog secret and the security signal would be LOST; redact-and-pass scrubs the secret VALUE and PRESERVES the finding ('Detected AWS key [redacted:secret] in config.py'). RESIDUAL: a prefix-less high-entropy token (e.g. a bare 40-char AWS *secret* key) is not regex-matchable by redact() OR FX-SEC-001 -- a documented residual, not universal coverage. The connector reads the finding MESSAGE only, NEVER the raw code snippet (region.snippet.text) -- data minimization. The ruleId/ref floor is not redacted. FX-SEC-001 (same catalog) is the fail-closed backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + redact-and-pass are built and harness-proven; the result message is redact-and-passed (a secret-bearing finding becomes scrubbed-evidence rather than being dropped), the raw snippet is never read. No credentials (file import). Gated on operator review + wiring the live file-watch / CI-collection path to a GatewaySink. To flip: set the SARIF report path/glob; wire the runtime ingest; ingest a real report; review before promoting.

- Gate: SARIF 2.1.0 is a FROZEN OASIS standard (no version drift): the result paths runs[].results[].{ruleId, level, message.text, locations[].physicalLocation.{artifactLocation.uri, region.startLine}} + runs[].tool.driver.name were verified against the OASIS schema 2026-06-08 and re-affirmed 2026-06-13.
- Gate: PII/SECRET: result message.text redact-and-passed (secret/PHI/PAN + email/phone) -- converts an FX-SEC-001 hard-reject of a secret-bearing finding into scrubbed-evidence so the security signal survives (SG-2026-06-13-E). The raw code snippet (region.snippet.text) is NEVER read. ruleId/ref floor un-redacted. FX-SEC-001 backstops secret/PHI/PAN.
- Gate: Live file-watch / CI-collection path is operator-runtime; no live ingest this cycle. Live flip gated on operator review + a real SARIF report ingest (ADR-0012).

## References

- spec: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
- spec-repo: https://github.com/oasis-tcs/sarif-spec
- auth: connectors/sarif/auth.md
