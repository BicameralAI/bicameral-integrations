# Bicameral Design Drift for Claude Code

**Status:** Initial implementation under #311 / #312–#314. Terminal Claude validation and managed installation remain open under #315–#316. The 2026-10-03 adversarial review identified activation dependencies that must close before support is claimed.

Bicameral Design Drift is a Claude Code plugin that presents Bicameral's existing Managed MCP design-plan drift analysis inside the active Claude coding session.

> **See when Claude's implementation plan has drifted from the accepted Bicameral design before implementation starts.**

## Documentation map

This package follows the repository's provider-documentation framework rather than treating provider docs as implementation-time browser research.

- [`../../README.md`](../../README.md) — host-plugin category contract.
- [`../README.md`](../README.md) — Claude Code provider-family API/SDK/type/source-precedence rules.
- [`references.md`](references.md) — canonical Anthropic provider docs, exact events/API methods consumed, version-sensitive assumptions, security facts, Bicameral dependencies, and refresh record.
- [`compatibility.json`](compatibility.json) — machine-readable provider version/API/event/authority declaration.
- [`../../../docs/INTEGRATION_DOCS_INDEX.md`](../../../docs/INTEGRATION_DOCS_INDEX.md) — repository-wide provider documentation source precedence and refresh policy.
- `docs/adr/0021-claude-code-plugin-design-drift-boundary.md` — integration architecture.
- `docs/prd/claude-code-design-drift-plugin.md` — product requirements.
- `docs/design/claude-code-design-drift-implementation-plan.md` — implementation sequencing.

Provider implementation work must update `references.md` and `compatibility.json` whenever it adds/removes a Claude event, Mods API call, version claim, or security-relevant runtime assumption.

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
references.md       # canonical provider + Bicameral documentation record
compatibility.json  # declared host/API/authority surface
README.md
```

Repository-level structural tests live in `tests/test_claude_design_drift_plugin.py` and behavior tests in `tests/test_claude_design_drift_behavior.py`.

## Planning boundary

The implementation reuses Bicameral MCP's existing Claude planning-complete boundary:

- settings/Mod event: `PostToolUse` / `classic.PostToolUse`;
- tool: `ExitPlanMode`;
- exact Plan bytes: `tool_response.plan` only;
- plan identity: SHA-256 of those exact bytes;
- required identity: Claude session id + turn id/tool-use identity + plan digest;
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
Design Drift: no candidate in analyzed scope
Design Drift: analysis completed · no drift conclusion asserted
Design Drift: analysis provider unavailable
Design Drift: analysis timed out
Design Drift: analysis failed validation
Design Drift: Bicameral MCP unavailable
```

The wording intentionally never upgrades an unclassified completed result, `no candidate`, timeout, unavailable, or incomplete analysis into global alignment, safety, approval, or permission to proceed.

`/bicameral-drift` prints the latest bounded result. Rich untrusted spec/candidate prose should move to a human-only Mod presentation surface rather than being injected into Claude's transcript by default.

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

Canonical provider references and their purpose live in [`references.md`](references.md), not as an ad hoc list in this README.

Key provider rules verified 2026-10-03:

- Mods require Claude Code `2.1.287` or later.
- A Mod is a Claude Code plugin containing JavaScript/TypeScript hook handlers.
- settings-hook events are exposed to Mods as `classic.<Event>` events.
- `$.mcp.call` calls a tool on a connected MCP server.
- Mods API calls can themselves be intercepted by earlier Mods in the chain.
- Claude Code generates exact-build TypeScript declarations under `.claude-plugin/types/`; those declarations outrank prose docs when they disagree.
- `claude plugin validate` statically reports the events and Mods API calls discovered in a package.

The relevant SDK-like surface for this integration is the **Claude Code Mods API plus generated types**, not the Claude Agent SDK.

Provider floor is not the same as Bicameral-qualified support. `compatibility.json` therefore leaves `tested_versions` empty until #316 produces retained real-host evidence.

## Activation dependencies exposed by adversarial review

The first implementation slice is not yet a functioning end-to-end drift feature on a clean install.

1. Current Bot Managed Preflight requires a live ClaimTrace to perform semantic analysis; absent that provider input, analysis is typed `provider_unavailable`. Activation therefore depends on the Bot live ClaimTrace producer (`BicameralAI/bicameral-bot#958` / `#1066`).
2. The connected MCP process requires Product context through its own Product-selection surface; daemon-side workspace resolution alone does not populate MCP process-local selection.
3. MCP may return normal preflight plus an additive CandidateSet review surface, which the host adapter must preserve and bind rather than treating the first JSON block as the whole response.
4. Returned boundary/Product/session/generation identity must be validated before display.
5. Claude-local Mod output is advisory presentation, not independently trusted governance evidence.

These are implementation dependencies, not reasons to duplicate Bot/MCP authority inside Integrations.

## Validation state

Completed in this slice:

- plugin package/manifest shape created;
- JSON/JS/package contracts exercised by repository tests;
- repository structural/security assertions added;
- current Bicameral MCP request/response shape reconciled from live repositories;
- provider documentation cataloged in `references.md`;
- provider-family documentation/source-precedence contract established in `plugins/claude-code/README.md`.

Still required before claiming supported/installable:

- `claude plugin validate` against an exact Claude Code build;
- real Claude load with generated `.claude-plugin/types/` checked/retained for that build;
- real `ExitPlanMode` event -> connected MCP -> daemon result -> status/review evidence;
- Product resolve/select composition for the connected MCP process;
- live semantic/ClaimTrace provider path;
- CandidateSet preservation and response-identity checks;
- version-skew/degraded/uninstall tests under #316;
- managed install/update/repair/uninstall composition under #315.

## Work tracking

- #311 - program umbrella
- #312 - package/descriptor/compatibility foundation
- #313 - host-neutral Managed MCP drift client
- #314 - planning lifecycle and Claude UX
- #315 - managed install/update/repair/uninstall composition
- #316 - security hardening and terminal acceptance

This package becomes supported only after #316 retains real Claude Code and real Bicameral end-to-end evidence for the exact candidate revisions.