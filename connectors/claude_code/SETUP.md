<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Claude Code — backend setup

Claude Code session-transcript JSONL turns as redact-and-pass governed evidence (local file import, no credential).

- **id** `claude_code` · **category** developer-ai · **trust tier** T0
- **status** live-ready · **available** True · **modes** passive

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "claude_code": {
      "enabled": true,
      "secrets": {}
    }
  }
}
```
## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run claude_code                 # fetch -> print screened emissions
python -m runtime.cli run-mods claude_code --mods dependency_risk
python -m runtime.cli run claude_code --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: user, assistant, summary
- PII posture: Transcripts are arbitrary local plaintext (file contents, command stdout/stderr, pasted text -> potential secrets/PII). The excerpt CONTENT is redact-and-passed (secret/PHI/PAN + email/phone scrubbed); the `[claude_code:kind] <id>` floor literal is left un-redacted but its id is opaque-id-validated ([A-Za-z0-9_-]{1,64}, else elided) so a poisoned id cannot carry an email. `cwd` is home-prefix-scrubbed for the common home layouts (drive-letter C:\Users\<name>, POSIX /Users//home//export/home, UNC \\server\Users\<name>, WSL \\wsl$\<distro>\home\<name> -> ~/...) so the OS username is not surfaced. FX-SEC-001 hard-rejects any residual secret/PHI/PAN. No credential or secret is stored in this package.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse surface (redact-and-pass + cwd scrub) is built and harness-proven; no credential to provision. Gated on operator review + the deferred live file-watch path. To flip: point the operator runtime at the local transcript directory; feed lines through ClaudeCodeConnector; wire GatewaySink; review before promoting.

- Gate: Source schema re-pinned against a REAL 6,008-line transcript 2026-06-12 (SG-2026-06-12-G): evidence types user/assistant carry message.content (text/thinking/tool_use/tool_result blocks); cwd/model/sessionId/uuid/timestamp(ISO) present. The documented `summary` type is ABSENT in the current format (kept legacy-tolerant); new types ai-title/pr-link/system/queue-operation exist and are intentionally NOT emitted this cycle (user/assistant turns are the evidence surface).
- Gate: PII: excerpt content redact-and-passed (secret/PHI/PAN + email/phone); cwd home-prefix scrubbed (no OS username); FX-SEC-001 is the un-bypassable backstop. source_id renamed claude-code -> claude_code (folder/descriptor alignment).
- Gate: Local file import (T0), no credential, no network. Live file-watch of ~/.claude/projects/<slug>/<session-id>.jsonl + history.jsonl (epoch-ms ts) are deferred (operator runtime). Live flip gated on operator review (ADR-0012).

## References

- data-usage: https://code.claude.com/docs/en/data-usage
- claude-directory: https://code.claude.com/docs/en/claude-directory
