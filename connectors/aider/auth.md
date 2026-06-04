# Aider Auth

Auth model recorded for the live cycle; this connector ships the **parse
surface** only (the live collection path is deferred).

- Default trust tier: T0
- Auth: Not applicable (git/file import).

## Deferred live paths

- Passive `git log` walk of a configured repository, filtering to Aider-attributed
  commits (`(aider)` author/committer or `Co-authored-by:` trailer).
- Opt-in `--analytics-log <file>.jsonl` ingest (structured, code-free).
- `.aider.chat.history.md` transcript parse — DEFERRED: no versioned/documented
  schema (markdown prose), scraping-prone; gated behind explicit opt-in when built.

Repositories and any local paths are provided by the operator runtime, never
stored in this package. See [references.md](references.md) and
[TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
