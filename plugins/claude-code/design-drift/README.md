# Bicameral Design Drift for Claude Code

**Status:** bounded implementation/remediation under #311 / #312–#314. The host-neutral Product-routing seam is implemented through merged `BicameralAI/bicameral-mcp#871` / PR #872. Terminal Claude validation and managed installation remain open under #315–#316. Live semantic analysis remains blocked on the Bot ClaimTrace provider path (`#958` / `#1066`).

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
- `docs/design/claude-code-design-drift-response-integrity-spike.md` — Product-routing / response-integrity checkpoint.

Provider implementation work must update `references.md` and `compatibility.json` whenever it adds/removes a Claude event, Mods API call, version claim, or security-relevant runtime assumption.

## Current implementation

The current slice remains deliberately thin:

```text
Claude Code MAIN THREAD classic.PostToolUse / ExitPlanMode
  -> hash exact tool_response.plan bytes
  -> session.start.cwd as routing hint only
  -> $.mcp.call("bicameral", "bicameral.workspace.resolve", { candidate_path })
  -> canonical product_id OR typed routing failure
  -> $.mcp.call("bicameral", "bicameral.product.select", { product_id })
  -> $.mcp.call("bicameral", "bicameral.preflight", { managed_planning })
  -> bounded response-integrity validation
  -> bicameral-bot Managed MCP result
  -> compact Claude status + /bicameral-drift review
```

All three MCP calls use Claude's existing connected `bicameral` MCP session. The plugin does not start or register a second server and does not inspect Bicameral workspace bindings itself.

The plugin does not become the drift engine. It consumes the existing Bicameral MCP / daemon contracts and preserves their authority boundaries.

## Package shape

```text
.claude-plugin/
  plugin.json
hooks/
  hooks.json
  register.js              # Claude lifecycle, command, serialized routing/preflight, ephemeral state
  provider.js              # main-thread eligibility + stable session routing hint
  routing.js               # host-neutral workspace.resolve -> product.select client boundary
  routing-presentation.js  # bounded typed routing status/review text
  drift.js                 # exact Plan hashing + host-neutral semantic result mapping
  integrity.js             # semantic response bounds, enum/digest/id validation, conflict rejection
references.md               # canonical provider + Bicameral documentation record
compatibility.json          # declared host/API/thread/routing/integrity/authority surface
README.md
```

Repository-level structural tests live in `tests/test_claude_design_drift_plugin.py`; host-neutral behavior, routing, and adversarial fixtures live in `tests/test_claude_design_drift_behavior.py`, `tests/test_claude_design_drift_routing.py`, and `tests/test_claude_design_drift_integrity.py`.

## Planning boundary

The implementation reuses Bicameral MCP's existing Claude planning-complete boundary:

- settings/Mod event: `PostToolUse` / `classic.PostToolUse`;
- tool: `ExitPlanMode`;
- **main-thread only** for v0.1; events carrying `agent_id` are ignored without mutating the main-thread result;
- exact Plan bytes: `tool_response.plan` only;
- plan identity: SHA-256 of those exact bytes;
- required identity: Claude session id + turn id/tool-use identity + Plan digest.

Product identity is not accepted from the Claude planning event. Any `product_id`-shaped field arriving from the host event is discarded before routing. The only Product id used for Product-scoped preflight is the exact canonical id returned by `bicameral.workspace.resolve` and then accepted by `bicameral.product.select` in the same MCP process.

The plugin never scrapes transcript/messages/conversation text to recover a missing Plan. If exact Plan bytes or required boundary identity are absent, it shows a limitation and does not call Bicameral.

## Product-routing posture

Claude's current `cwd` is not Product identity. Anthropic documents that it can change as Claude changes directory or enters a worktree.

The plugin therefore captures `session.start.cwd` once as a provider-authored **routing hint** and does not refresh that hint from later `PostToolUse.cwd` values. Clear/compact SessionStart events preserve the already captured hint.

The accepted routing flow is now:

```text
session.start.cwd routing hint
  -> bicameral.workspace.resolve
  -> canonical product_id or typed failure
  -> bicameral.product.select(product_id)
  -> Product-scoped preflight
```

The routing hint must belong to the same Claude session as the planning boundary. Missing or mismatched session routing identity fails visibly before an MCP call.

`workspace.resolve` remains read-only. A successful resolve is accepted only when it explicitly reports `canonical_write: "none"` and `product_selection_changed: false`. Resolve does not authorize Product-scoped calls. The plugin separately requires `product.select` to echo the exact daemon-resolved Product id before invoking preflight.

Distinct routing outcomes remain visible, including unbound, repair-required, ambiguous, unsafe/invalid routing hint, malformed/conflicting routing response, MCP unavailable/protocol/capability failures, and Product-selection failure. These states are never rewritten as alignment or permission to proceed.

No path/git/transcript/model fallback exists. The local candidate path is not retained in result state or emitted through `/bicameral-drift`.

## Process-local selection and concurrency

`bicameral.product.select` establishes MCP-process-local Product context. For that reason, route -> select -> preflight chains are serialized across planning boundaries.

If a newer Plan boundary arrives while another boundary is in flight, the plugin coalesces work onto the newest active boundary instead of overlapping Product-selection state. A superseded boundary may finish a read-only resolve already in progress, but it is stopped before selection when staleness is observed. If staleness occurs after selection returns, no Product-scoped preflight is issued for that stale boundary; the queued current boundary re-resolves and re-selects before its own preflight.

This serialization is client coordination only. It does not create Product authority in Integrations.

## Response integrity

Before a semantic result becomes persistent Mod state or transcript-visible output, the package applies a bounded integrity layer:

- maximum 16 semantic MCP content items;
- maximum 262,144 aggregate semantic JSON/text characters;
- maximum 256 candidates;
- routing responses separately limited to 8 content items and 32,768 aggregate characters;
- byte-equivalent duplicate semantic surfaces may be tolerated;
- conflicting Managed Preflight surfaces fail closed;
- conflicting CandidateSet surfaces fail closed;
- conflicting routing/selection surfaces fail closed;
- mixed success and typed-error semantic surfaces fail closed;
- Managed Preflight outcome/status/class values must match the current closed Bot enums;
- Plan/spec/CandidateSet digests must be lowercase `sha256:<64 hex>` values;
- CandidateSet and candidate identities must be UUIDs;
- returned boundary identity must match the exact request;
- CandidateSet Product/session/Plan/spec binding must match the returned/requested identity;
- Product selection must echo the exact Product id returned by workspace resolution.

The integrity layer is a presentation-integrity defense. It does **not** make the Claude Mod chain canonical or independently trusted evidence.

## Automatic preflight

For a new exact `(host, session, turn, plan_digest)` main-thread boundary, the Mod schedules work through `$.clock.after(0, ...)`, returns the Claude hook immediately, then performs the serialized Product routing and Bicameral preflight chain.

Duplicate delivery is suppressed. `/bicameral-drift refresh` coalesces with identical work that is already scheduled or in flight rather than creating a duplicate request.

Plugin/UI/scheduling failures are contained locally and fail open with respect to Claude execution. Design Drift must never prevent the user from continuing normal Claude work merely because its advisory presentation failed.

## User experience

The Mod registers:

```text
/bicameral-drift
/bicameral-drift refresh
```

Automatic results are shown with `$.ui.status`. Contradictions also raise a bounded toast.

The wording intentionally never upgrades an unclassified completed result, `no candidate`, timeout, unavailable, routing failure, integrity failure, or incomplete analysis into global alignment, safety, approval, or permission to proceed.

`/bicameral-drift` prints only a bounded typed summary. Raw candidate text, governing-spec prose, provider limitation details, local workspace paths, and source excerpts do not enter Claude's transcript through this command.

## Authority boundary

- `bicameral-bot` owns governing-spec resolution, drift/candidate semantics, Product state, promotion/rejection semantics, and canonical receipts.
- `bicameral-mcp` / the daemon owns host-neutral capability transport, workspace-to-Product routing, Product selection validation, and Product-scoped tool access.
- this plugin owns Claude lifecycle adaptation, MCP invocation, ephemeral display state, and presentation.
- the human and existing Bicameral daemon authority own consequence-bearing confirmation.

The v0.1.0 compatibility contract declares canonical state mutation, tool approval, prompt rewrite, tool rewrite, autonomous confirmation, direct HTTP, and arbitrary network destinations as **false**.

The implementation uses only `command.register`, `clock.after`, `mcp.call`, `ui.status`, and `ui.toast`.

## Provider requirements

Canonical provider references and their purpose live in [`references.md`](references.md), not as an ad hoc list in this README.

The relevant SDK-like surface for this integration is the **Claude Code Mods API plus generated types**, not the Claude Agent SDK.

Provider floor is not the same as Bicameral-qualified support. `compatibility.json` therefore leaves `tested_versions` empty until #316 produces retained real-host evidence.

## Activation dependencies

The package is not yet a supported end-to-end drift feature on a clean install.

1. Current Bot Managed Preflight requires a live ClaimTrace to perform semantic analysis; absent that provider input, analysis is typed `provider_unavailable`. Activation depends on the Bot live ClaimTrace producer (`BicameralAI/bicameral-bot#958` / `#1066`) or an accepted successor.
2. Claude-local Mod output remains advisory presentation because earlier Mods can intercept host/API traffic.
3. Real Claude generated types, plugin validation, and terminal behavior remain unqualified until #316.
4. Managed install/update/repair/uninstall composition remains #315.

The former Product-routing blocker `BicameralAI/bicameral-mcp#871` is complete and consumed here. That removes a transport/routing blocker; it does not imply live semantic activation or release readiness.

## Validation state

Completed in the current branch:

- plugin package/manifest shape;
- exact Plan boundary hashing;
- main-thread-only planning gate;
- stable session-start routing-hint capture;
- host-neutral `workspace.resolve -> product.select -> preflight` composition;
- rejection of host/event supplied Product authority;
- serialization/coalescing around MCP-process-local Product selection;
- typed routing failures and routing-response bounds;
- multi-content semantic MCP parsing;
- exact response-boundary/CandidateSet binding checks;
- conflicting semantic payload rejection;
- semantic response size/candidate bounds;
- closed enum/digest/UUID validation before transcript rendering;
- refresh/in-flight coalescing;
- fail-open plugin presentation behavior;
- repository structural/security assertions;
- provider documentation framework and compatibility declaration.

Still required before claiming supported/installable:

- `claude plugin validate` against an exact Claude Code build;
- real Claude load with generated `.claude-plugin/types/` checked/retained for that build;
- live semantic/ClaimTrace provider path;
- real `ExitPlanMode -> resolve -> select -> preflight -> daemon -> status/review` evidence;
- version-skew/degraded/uninstall tests under #316;
- managed install/update/repair/uninstall composition under #315.

## Work tracking

- #311 - program umbrella
- #312 - package/descriptor/compatibility foundation
- #313 - host-neutral Managed MCP drift client
- #314 - planning lifecycle and Claude UX
- #315 - managed install/update/repair/uninstall composition
- #316 - security hardening and terminal acceptance
- #319 - Product-routing / response-integrity checkpoint
- #320 - documentation binding for the checkpoint
- BicameralAI/bicameral-mcp#871 / PR #872 - completed host-neutral workspace resolve seam
- BicameralAI/bicameral-bot#1340 / PR #1343 - completed cross-repo workspace.resolve conformance reconciliation

This package becomes supported only after #316 retains real Claude Code and real Bicameral end-to-end evidence for the exact candidate revisions.
