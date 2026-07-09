# Session Handoff

## Last Session Summary
Recorded Linear + Google Drive as **flip-ready, NOT yet Live**, opened the mcp UI
work item for their config surfaces, and verified the qor-logic governance corpus
is distributed in-sync to the repo agents. No connector was promoted to Live.

## Completed This Session
- **Linear + Google Drive → flip-ready, NOT yet Live** (PR #90). Each descriptor's
  `live_readiness` + a closing `wire_gates` entry + `references.md` readiness now
  state the explicit pre-Live gate: code-complete and harness-proven against a
  reference sink, but unverified against the live API with real secrets. `status`
  stays `live-ready` (no `live` enum — Live = operator wires real secrets + verifies).
  `connectors/index.json` + both `SETUP.md` regenerated (LF-pinned, byte-exact).
- **mcp UI work item opened** — BicameralAI/bicameral-mcp#572 — to build the Linear +
  Google Drive connector config UI against the FX-CFG-001 descriptor contract; a
  back-reference pointer was added to `docs/UI_RENDERING_SPEC.md` (PR #89).
- **qor-logic corpus distribution verified in-sync** — `qor-logic install --host claude
  --scope repo` ran idempotent (zero diff); `.claude/agents/` + `.claude/skills/`
  already carry the current v0.103.1 corpus.

## Open Work
- **Live flips (operator-gated):** wire `GatewaySink` + real secrets — Linear API key;
  Google durable credential via `RefreshTokenSecretResolver` (or service-account JSON
  at the operator runtime) — run the live test, review, then promote to Live.
- **mcp#572** — UI build (cross-repo).
- **Mod fan-out** — 10 Scoped mods remain (3 of 13 built).
- **Connector fan-out** — 24 connectors still need `config.json` + `SETUP.md` + a
  `RUNNERS` wire to match the Linear/Google Drive exemplars.
- Selected BACKLOG: B5 (branch protection on `main`), B10 (connector module-docstring
  freshness). B15 CLOSED 2026-07-08 (superseded by the #226 v2 external-ingest migration).

## Known Issues
- **No connector is Live yet.** All 26 are Beta; Linear + Google Drive are flip-ready
  (code-complete, harness-proven) but unverified against live APIs.
- **Shared worktree with Codex:** branch-first every cycle; never `git reset --hard`
  (Codex's `mods/` edits may be uncommitted).

## Next Steps
1. Operator: wire + live-test Linear, then Google Drive; promote each on review.
2. mcp team: build the #572 connector-config UI.
3. Resume the mod fan-out (next Scoped mod).
