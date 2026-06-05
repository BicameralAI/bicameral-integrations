# Claude Code Connector

Read-only evidence connector: it parses Claude Code session transcripts into
neutral `Observation`s. **Status: Beta** (ADR-0012; catalog developer-AI
tooling, priority P0, default trust tier T0). From the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Passive** — Claude Code writes session transcripts as local JSONL at
  `~/.claude/projects/<project-slug>/<session-id>.jsonl`. Each evidence line
  (`user` / `assistant` / `summary`) maps to one neutral `Observation`
  (`parse_session_line`); meta/unknown line types are skipped. No canonical
  writes — evidence adapter, not state authority (ADR-0008).

The live boundary — the file-watch path, the global `~/.claude/history.jsonl`,
a git-attribution path (`Co-Authored-By: Claude`, off in this repo by stealth
policy), and secret resolution — stays in the operator runtime (see
[`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its `runtime.deliver_poll` → reference sink path is proven
end-to-end by `runtime/tests/test_runtime.py`, with **zero cross-repo
dependency**. Live (gateway emission) remains gated on bicameral-bot #109.

## Surface

- `parse_session_line(line)` — one transcript line → `Observation` or `None`.
  Keeps `user`/`assistant`/`summary`; user `content` (str or block list),
  assistant `text`/`tool_use` blocks, and `summary` text → excerpt, with a
  `[claude-code:{kind}] {uuid}` terminal fallback (the schema is unversioned and
  heterogeneous, so every field is defended and unknown line types are skipped).
- `ClaudeCodeConnector` — connector identity and capabilities (`PASSIVE`);
  `observations` accepts one line or a `{"lines": [...]}` batch and drops the
  non-evidence lines.

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
