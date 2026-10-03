# Bicameral Design Drift for Claude Code

**Status:** bounded implementation/remediation under #311 / #312–#314. Terminal Claude validation and managed installation remain open under #315–#316. Product routing remains blocked on `BicameralAI/bicameral-mcp#871`; live semantic analysis remains blocked on the Bot ClaimTrace provider path (`#958` / `#1066`).

Bicameral Design Drift is a Claude Code plugin that presents Bicameral's existing Managed MCP design-plan drift analysis inside the active Claude coding session.

> **See when Claude's implementation plan has drifted from the accepted Bicameral design before implementation starts.**

## Documentation map

This package follows the repository's provider-documentation framework rather than treating provider docs as implementation-time browser research.

- [`../../README.md`](../../README.md) — host-plugin category contract.
- [`../README.md`](../README.md) — Claude Code provider-family API/SDK/type/source-precedence rules.
- [`references.md`](references.md) — canonical Anthropic provider docs, exact events/API methods consumed, version-sensitive assumptions, security facts, Bicameral dependencies, and refresh record.
- [`compatibility.json`](compatibility.json) — machine-readable provider version/API/event/thread/routing/integrity/authority declaration.
- [`../../../docs/INTEGRATION_DOCS_INDEX.md`](../../../docs/INTEGRATION_DOCS_INDEX.md) — repository-wide provider documentation source precedence and refresh policy.
- `docs/adr/0021-claude-code-plugin-design-drift-boundary.md` — integration architecture.
- `docs/prd/claude-code-design-drift-plugin.md` — product requirements.
- `docs/design/claude-code-design-drift-implementation-plan.md` — implementation sequencing.
- `docs/design/claude-code-design-drift-response-integrity-spike.md` — current Product-routing / response-integrity remediation checkpoint.

Provider implementation work must update `references.md` and `compatibility.json` whenever it adds/removes a Claude event, Mods API call, version claim, or security-relevant runtime assumption.

## Current implementation

The current slice remains deliberately thin:

```text
Claude Code MAIN THREAD classic.PostToolUse / ExitPlanMode
  -> hash exact tool_response.plan bytes
  -> $.mcp.call("bicameral", "bicameral.preflight", { managed_planning })
  -> bounded response-integrity validation
  -> existing Bicameral MCP / daemon capability
  -> bicameral-bot Managed MCP result
  -> compact Claude status + /bicameral-drift review
```

The plugin does not become the drift engine. It consumes the already-connected `bicameral` MCP server and the current `bicameral.preflight` managed-planning contract.

## Package shape

```text
.claude-plugin/
  plugin.json
hooks/
  hooks.json
  register.js       # Claude lifecycle, command, status, MCP call, in-flight state
  provider.js       # main-thread eligibility + stable session routing hint
  drift.js          # exact Plan hashing + host-neutral result mapping
  integrity.js      # response bounds, enum/digest/id validation, conflict rejection
references.md       # canonical provider + Bicameral documentation record
compatibility.json  # declared host/API/thread/routing/integrity/authority surface
README.md
```

Repository-level structural tests live in `tests/test_claude_design_drift_plugin.py`; host-neutral behavior and adversarial fixtures live in `tests/test_claude_design_drift_behavior.py` and `tests/test_claude_design_drift_integrity.py`.

## Planning boundary

The implementation reuses Bicameral MCP's existing Claude planning-complete boundary:

- settings/Mod event: `PostToolUse` / `classic.PostToolUse`;
- tool: `ExitPlanMode`;
- **main-thread only** for v0.1; events carrying `agent_id` are ignored without mutating the main-thread result;
- exact Plan bytes: `tool_response.plan` only;
- plan identity: SHA-256 of those exact bytes;
- required identity: Claude session id + turn id/tool-use identity + Plan digest;
- optional Product id is forwarded only when already present on the host event.

The plugin never scrapes transcript/messages/conversation text to recover a missing Plan. If exact Plan bytes or required boundary identity are absent, it shows a limitation and does not call Bicameral.

## Product-routing posture

Claude's current `cwd` is not Product identity. Anthropic documents that it can change as Claude changes directory or enters a worktree.

The plugin therefore captures `session.start.cwd` once as a provider-authored **routing hint** and does not refresh that hint from later `PostToolUse.cwd` values.

That captured hint is intentionally dormant until `bicameral-mcp#871` exposes the daemon-owned `workspace.resolve` read through MCP. The intended future flow remains:

```text
session.start.cwd routing hint
  -> bicameral.workspace.resolve
  -> canonical product_id or typed failure
  -> bicameral.product.select(product_id)
  -> Product-scoped preflight
```

No path/git/transcript/model fallback exists.

## Response integrity

Before a result becomes persistent Mod state or transcript-visible output, the package now applies a bounded integrity layer:

- maximum 16 MCP content items;
- maximum 262,144 aggregate JSON/text characters;
- maximum 256 candidates;
- byte-equivalent duplicate semantic surfaces may be tolerated;
- conflicting Managed Preflight surfaces fail closed;
- conflicting CandidateSet surfaces fail closed;
- mixed success and typed-error semantic surfaces fail closed;
- Managed Preflight outcome/status/class values must match the current closed Bot enums;
- Plan/spec/CandidateSet digests must be lowercase `sha256:<64 hex>` values;
- CandidateSet and candidate identities must be UUIDs;
- returned boundary identity must match the exact request;
- CandidateSet Product/session/Plan/spec binding must match the returned/requested identity.

The integrity layer is a presentation-integrity defense. It does **not** make the Claude Mod chain canonical or independently trusted evidence.

## Automatic preflight

For a new exact `(host, session, turn, plan_digest)` main-thread boundary, the Mod schedules preflight through `$.clock.after(0, ...)`, returns the Claude hook immediately, and performs the Bicameral call in the background.

Duplicate delivery is suppressed. `/bicameral-drift refresh` now coalesces with identical work that is already scheduled or in flight rather than creating a duplicate request.

Plugin/UI/scheduling failures are contained locally and fail open with respect to Claude execution. Design Drift must never prevent the user from continuing normal Claude work merely because its advisory presentation failed.

## User experience

The Mod registers:

```text
/bicameral-drift
/bicameral-drift refresh
```

Automatic results are shown with `$.ui.status`. Contradictions also raise a bounded toast.

The wording intentionally never upgrades an unclassified completed result, `no candidate`, timeout, unavailable, integrity failure, or incomplete analysis into global alignment, safety, approval, or permission to proceed.

`/bicameral-drift` prints only a bounded typed summary. Raw candidate text, governing-spec prose, provider limitation details, and source excerpts do not enter Claude's transcript through this command.

## Authority boundary

- `bicameral-bot` owns governing-spec resolution, drift/candidate semantics, Product state, promotion/rejection semantics, and canonical receipts.
- `bicameral-mcp` / the accepted daemon API owns the host-neutral capability/transport and Product-routing boundary.
- this plugin owns Claude lifecycle adaptation, MCP invocation, ephemeral display state, and presentation.
- the human and existing Bicameral daemon authority own consequence-bearing confirmation.

The v0.1.0 compatibility contract declares canonical state mutation, tool approval, prompt rewrite, tool rewrite, autonomous confirmation, direct HTTP, and arbitrary network destinations as **false**.

The implementation uses only `command.register`, `clock.after`, `mcp.call`, `ui.status`, and `ui.toast`.

## Provider requirements

Canonical provider references and their purpose live in [`references.md`](references.md), not as an ad hoc list in this README.

The relevant SDK-like surface for this integration is the **Claude Code Mods API plus generated types**, not the Claude Agent SDK.

Provider floor is not the same as Bicameral-qualified support. `compatibility.json` therefore leaves `tested_versions` empty until #316 produces retained real-host evidence.

## Activation dependencies

The package is not yet a functioning end-to-end drift feature on a clean install.

1. Current Bot Managed Preflight requires a live ClaimTrace to perform semantic analysis; absent that provider input, analysis is typed `provider_unavailable`. Activation depends on the Bot live ClaimTrace producer (`BicameralAI/bicameral-bot#958` / `#1066`).
2. The connected MCP process requires Product context through its own Product-selection surface. Host-neutral workspace resolution is tracked in `BicameralAI/bicameral-mcp#871`.
3. Claude-local Mod output remains advisory presentation because earlier Mods can intercept host/API traffic.
4. Real Claude generated types and terminal behavior remain unqualified until #316.

These are implementation dependencies, not reasons to duplicate Bot/MCP authority inside Integrations.

## Validation state

Completed in the current branch:

- plugin package/manifest shape;
- exact Plan boundary hashing;
- main-thread-only planning gate;
- stable session-start routing-hint capture;
- multi-content MCP parsing;
- exact response-boundary/CandidateSet binding checks;
- conflicting semantic payload rejection;
- response size/candidate bounds;
- closed enum/digest/UUID validation before transcript rendering;
- refresh/in-flight coalescing;
- fail-open plugin presentation behavior;
- repository structural/security assertions;
- provider documentation framework and compatibility declaration.

Still required before claiming supported/installable:

- `claude plugin validate` against an exact Claude Code build;
- real Claude load with generated `.claude-plugin/types/` checked/retained for that build;
- MCP #871 resolve/select composition;
- live semantic/ClaimTrace provider path;
- real `ExitPlanMode` -> MCP -> daemon -> status/review evidence;
- version-skew/degraded/uninstall tests under #316;
- managed install/update/repair/uninstall composition under #315.

## Work tracking

- #311 - program umbrella
- #312 - package/descriptor/compatibility foundation
- #313 - host-neutral Managed MCP drift client
- #314 - planning lifecycle and Claude UX
- #315 - managed install/update/repair/uninstall composition
- #316 - security hardening and terminal acceptance
- #319 - current Product-routing / response-integrity checkpoint
- #320 - documentation binding for the checkpoint
- BicameralAI/bicameral-mcp#871 - host-neutral workspace resolve seam

This package becomes supported only after #316 retains real Claude Code and real Bicameral end-to-end evidence for the exact candidate revisions.