# Claude Code Connector

Provider-facing Claude Code adapter. **Status: Prototype** (catalog
developer-AI tooling, priority P0, default trust tier T0). From the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Passive** — Claude Code writes session transcripts as local JSONL at
  `~/.claude/projects/<project-slug>/<session-id>.jsonl`. Each evidence line
  (`user` / `assistant` / `summary`) maps to one neutral `Observation`
  (`parse_session_line`); meta/unknown line types are skipped. No canonical
  writes — evidence adapter, not state authority (ADR-0008).

The live file-watch path, the global `~/.claude/history.jsonl`, and a
git-attribution path (`Co-Authored-By: Claude`, off in this repo by stealth
policy) are deferred this cycle (see [`auth.md`](auth.md)); this connector is
the parse surface only.

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
