# Bicameral Design Drift for Claude Code

**Status:** Initial implementation under #311 / #312–#314. Terminal Claude validation and managed installation remain open under #315–#316.

Bicameral Design Drift is a Claude Code plugin that presents Bicameral's existing Managed MCP design-plan drift analysis inside the active Claude coding session.

> **See when Claude's implementation plan has drifted from the accepted Bicameral design before implementation starts.**

## Current implementation

The first runnable slice is deliberately thin:

```text
Claude Code classic.PostToolUse / ExitPlanMode
  -> hash exact tool_response.plan bytes
  -> $.mcp.call("bicameral", "bicameral.preflight", { managed_planning })
  -> existing Bicameral MCP / daemon capability
  -> bicameral-bot Managed MCP drift analysis
  -> compact Claude status + /bicameral-drift review
```

The plugin does not become the drift engine. It consumes the already-connected `bicameral` MCP server and the current `bicameral.preflight` managed-planning contract.

## Package shape

```text
.claude-plugin/
  plugin.json
hooks/
  hooks.json
  register.js       # Claude lifecycle, command, status, MCP call
  drift.js          # exact boundary hashing + response normalization
compatibility.json  # declared host/API/authority surface
README.md
```

Repository-level structural tests live in `tests/test_claude_design_drift_plugin.py`.

## Planning boundary

The implementation reuses Bicameral MCP's existing Claude planning-complete boundary:

- settings/Mod event: `PostToolUse` / `classic.PostToolUse`;
- tool: `ExitPlanMode`;
- exact Plan bytes: `tool_response.plan` only;
- plan identity: SHA-256 of those exact bytes;
- required identity: Claude session id + turn id + plan digest;
- optional Product id is forwarded only when already present on the host event.

The plugin never scrapes transcript/messages/conversation text to recover a missing Plan. If exact Plan bytes or required boundary identity are absent, it shows a limitation and does not call Bicameral.

## Automatic preflight

For a new exact `(host, session, turn, plan_digest)` boundary, the Mod schedules preflight through `$.clock.after(0, ...)`, returns the Claude hook immediately, and performs the Bicameral call in the background. This preserves the accepted advisory/non-blocking posture.

Duplicate delivery of the same boundary is suppressed inside the Mod. The daemon/MCP path remains responsible for its own idempotency and canonical authority.

## User experience

The Mod registers:

```text
/bicameral-drift
/bicameral-drift refresh
```

Automatic results are shown with `$.ui.status`. Contradictions also raise a bounded toast. Examples:

```text
Design Drift: analyzing…
Design Drift: contradiction detected
Design Drift: proposed differences
Design Drift: no actionable difference in analyzed scope
Design Drift: analysis provider unavailable
Design Drift: analysis timed out
Design Drift: analysis failed validation
Design Drift: Bicameral MCP unavailable
```

The wording intentionally never upgrades `no candidate`, timeout, unavailable, or incomplete analysis into global alignment, safety, approval, or permission to proceed.

`/bicameral-drift` prints the latest bounded result, including outcome, analysis status/classes, exact spec-binding digest when returned by Bicameral, candidate count when present, and explicit limitations. `refresh` reruns the current captured boundary.

## Authority boundary

- `bicameral-bot` owns governing-spec resolution, drift/candidate semantics, Product state, promotion/rejection semantics, and canonical receipts.
- `bicameral-mcp` / the accepted daemon API owns the host-neutral capability/transport boundary.
- this plugin owns Claude lifecycle adaptation, MCP invocation, ephemeral display state, and presentation.
- the human and existing Bicameral daemon authority own consequence-bearing confirmation.

The v0.1.0 compatibility contract declares:

- canonical state mutation: **false**;
- tool approval: **false**;
- prompt rewrite: **false**;
- tool rewrite: **false**;
- autonomous confirmation: **false**;
- direct HTTP: **false**;
- arbitrary network destinations: **false**.

The implementation uses only `command.register`, `clock.after`, `mcp.call`, `ui.status`, and `ui.toast`.

## Provider requirements

Official Anthropic documentation, verified 2026-10-03, states Mods require Claude Code `2.1.287` or later and that a Mod is a plugin with `.claude-plugin/plugin.json`, `hooks/hooks.json`, and a JavaScript/TypeScript hooks module. Claude Code can call an already connected MCP server through `$.mcp.call`.

Provider floor is not the same as Bicameral-qualified support. `compatibility.json` therefore leaves `tested_versions` empty until #316 produces retained real-host evidence.

Official references:

- https://code.claude.com/docs/en/plugins/mods/create
- https://code.claude.com/docs/en/plugins/mods/reference
- https://code.claude.com/docs/en/plugins/mods/api

## Validation state

Completed in this slice:

- plugin package/manifest shape created;
- JS syntax checked during authoring;
- JSON contracts parsed during authoring;
- repository structural/security assertions added;
- current Bicameral MCP request/response shape reconciled from the live repositories.

Still required before claiming supported/installable:

- `claude plugin validate` against an exact Claude Code build;
- real Claude load with generated `/plugin-types` checked against the source;
- real `ExitPlanMode` event -> connected MCP -> daemon result -> status/command evidence;
- version-skew/degraded/uninstall tests under #316;
- managed install/update/repair/uninstall composition under #315.

## Work tracking

- #311 - program umbrella
- #312 - package/descriptor/compatibility foundation
- #313 - host-neutral Managed MCP drift client
- #314 - planning lifecycle and Claude UX
- #315 - managed install/update/repair/uninstall composition
- #316 - security hardening and terminal acceptance

## Architecture documents

- `docs/adr/0021-claude-code-plugin-design-drift-boundary.md`
- `docs/prd/claude-code-design-drift-plugin.md`
- `docs/design/claude-code-design-drift-implementation-plan.md`

This package becomes supported only after #316 retains real Claude Code and real Bicameral end-to-end evidence for the exact candidate revisions.
