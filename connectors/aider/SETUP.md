<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Aider — backend setup

Aider-attributed git commits as read-only developer-AI provenance evidence (commit subject redact-and-passed; the human author name is retained as the provenance signal).

- **id** `aider` · **category** source-control / developer-AI tooling · **trust tier** T0
- **status** live-ready · **available** True · **modes** passive

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "aider": {
      "enabled": true,
      "secrets": {},
      "runtime": {
        "repo_path": "<Git repository / working copy path>"
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `repo_path` | True | — | Path to the git repo the operator runtime walks (git-log import). Aider auto-commits its edits and attributes them; only attributed commits are ingested. Read-only — no canonical writes (ADR-0008). |

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run aider                 # fetch -> print screened emissions
python -m runtime.cli run-mods aider --mods dependency_risk
python -m runtime.cli run aider --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: commit
- PII posture: The commit SUBJECT is redact-and-passed (secret/PHI/PAN + email/phone scrubbed; F3 / SG-2026-06-13-A — a developer may paste a token/email into a commit message). The git AUTHOR NAME is RETAINED (e.g. 'Dev Example (aider)'): this connector exists to attribute developer-AI work, so *which human ran the AI pair-programmer* is the evidence at trust tier T0 — the deliberate opposite of the fathom/claude_code name-drop (F4 / SG-2026-06-13-B). Only author_name is read, never author_email, so no contact handle leaks. The commit hash / 'aider-commit' floor is an opaque id and is NOT redacted. FX-SEC-001 hard-screens secret/PHI/PAN as the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + attribution detection + redact-and-pass on the subject are built and harness-proven; the author name is retained as deliberate git provenance. No network credentials (local git import). Gated on operator review + wiring the live git-log walk to a GatewaySink. To flip: set the repo path; wire the runtime git-log import; verify against an attributed commit; review before promoting.

- Gate: Contract re-verified live 2026-06-13 (aider.chat/docs/git.html): '(aider)' appended to BOTH git author + committer name by default; committer-only for dirty-file commits; --attribute-co-authored-by opt-in Co-authored-by trailer. _attributed_by precedence (author -> committer -> co-author) matches.
- Gate: PII: commit subject redact-and-passed (secret/PHI/PAN + email/phone); author NAME retained as intentional T0 git provenance (SG-2026-06-13-B); author_email never read; opaque hash floor un-redacted. FX-SEC-001 backstops secret/PHI/PAN.
- Gate: Live git-log walk, the --analytics-log JSONL, and the .aider.chat.history.md transcript are operator-runtime; no live ingest this cycle. Live flip gated on operator review + a real git-log import (ADR-0012).

## References

- git-attribution: https://aider.chat/docs/git.html
- auth: connectors/aider/auth.md
- contract: connectors/aider/references.md
