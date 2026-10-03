# ADR-0021: Claude Code Design Drift plugin boundary

**Date:** 2026-10-03  
**Status:** Proposed  
**Level:** L2 cross-repository integration boundary  
**Program:** #311  
**Relates to:** ADR-0008, ADR-0013, ADR-0015, ADR-0017, ADR-0019  
**Upstream Product authority:** `BicameralAI/bicameral-bot#979` and the governed Managed MCP drift-aware continuation specification  
**Implementation children:** #312, #313, #314, #315, #316

## Context

Bicameral already has an accepted Product outcome and governed runtime design for design-plan drift. The Managed MCP flow runs an advisory preflight after Planning, binds one exact governing specification revision, analyzes the completed plan against that source, and returns bounded `DecisionCandidate`/contradiction/limitation state. Candidate working state is session-scoped. Canonical Product mutation remains behind daemon authority and explicit human confirmation.

That capability currently exists primarily as a host-neutral MCP/daemon interaction. As Bicameral moves toward an installable developer product, Claude Code has gained a native extension mechanism that can make the same capability visible at the point where a developer plans and implements work.

Anthropic calls this mechanism a **Mod**. A Mod is not an HTTP API or an MCP server. It is JavaScript/TypeScript code packaged as a Claude Code plugin and executed inside the Claude Code process. It can handle lifecycle/tool/command/UI events, share state between handlers, make network calls, and draw interactive terminal/Desktop UI.

Current Anthropic documentation, verified 2026-10-03:

- Mods overview: https://code.claude.com/docs/en/plugins/mods/overview
- Mods reference: https://code.claude.com/docs/en/plugins/mods/reference
- Plugin installation: https://code.claude.com/docs/en/plugins/install

Important current provider facts:

1. Mods require Claude Code `2.1.287` or later.
2. A Mod installs as a normal Claude plugin, normally through a plugin marketplace.
3. Hooks execute in-process and may observe, rewrite, or answer events.
4. Mods can draw panes/bands and replace selected UI in the interactive terminal and supported Claude Desktop Code surfaces.
5. Hooks may still run in surfaces where custom Mod drawing is not shown, so a text/command fallback is required.
6. Mods run with the user's permissions and are not sandboxed. They can read/write files, start processes, make network requests, inspect session data, rewrite events, and even approve tool calls if authored to do so.
7. Current event documentation does not expose a stable event literally named `PlanningComplete`.

Those facts make a Claude-native Design Drift experience valuable, but they also make the authority boundary load-bearing. Claude's host runtime must not become a second Bicameral governance engine merely because it now offers powerful hooks.

## Problem

Without a first-class host integration, a developer can complete a Claude plan and proceed into implementation without seeing the existing Bicameral drift analysis at the moment it matters most.

A weak implementation would solve this by duplicating or guessing semantics inside Claude:

- parsing the assistant's plan prose;
- guessing which spec is governing;
- calculating "alignment" locally;
- treating a Claude hook as Product authority;
- rewriting or blocking tool calls based on plugin-local conclusions;
- maintaining a second CandidateSet or approval lifecycle;
- hand-editing Claude configuration through a plugin-specific installer.

That would create exactly the type of semantic drift Bicameral is intended to prevent.

We need a Claude-native surface without moving authority into Claude.

## Decision

### 1. Ship Design Drift as a Claude Code plugin owned by `bicameral-integrations`

The Claude-specific package, lifecycle adaptation, rendering, commands, compatibility metadata, and provider-specific tests live in this repository.

The integration is a thin host client over existing Bicameral capability:

```text
Claude Code
    |
    v
Bicameral Claude plugin / Mod
    |  host lifecycle + presentation only
    v
existing Bicameral MCP / daemon capability
    |
    v
bicameral-bot Managed MCP drift analysis
    |
    v
daemon-owned Product / Candidate / Decision authority
```

The plugin may normalize host and transport mechanics. It may not redefine the meaning of the Bicameral result.

### 2. Add `plugins/` as a repository packaging category

Create a top-level `plugins/` category for installable packages that run inside third-party host/plugin runtimes.

Initial shape:

```text
plugins/
  README.md
  claude-code/
    design-drift/
      .claude-plugin/
        plugin.json
      hooks/
        hooks.json
        register.ts
      README.md
      tests/
```

`plugins/` is a **packaging and host-integration category**. It is not a new state-authority category.

This is intentionally distinct from the existing `mods/` directory. In this repository, `mods/` already means Bicameral EM-safe advisory processors that consume evidence and emit advisory annotations. Anthropic's use of the word "Mod" describes executable functions inside Claude Code. Putting both concepts under `mods/` would make code ownership and security review ambiguous.

### 3. Preserve the existing cross-repository authority split

#### `bicameral-bot` owns

- accepted Product state;
- exact governing-spec resolution/binding;
- semantic extraction and drift analysis;
- deterministic analysis/solver results where applicable;
- CandidateSet semantics and lifecycle;
- Product policy;
- promotion/rejection semantics;
- approval/signoff semantics;
- canonical append/replay;
- canonical receipts.

#### `bicameral-mcp` / daemon API owns

- host-neutral developer-host capability exposure;
- transport/tool/session contracts;
- connection/authentication as already governed;
- the existing Managed MCP request/response path or its accepted successor;
- host-neutral preparation/confirmation calls when authorized.

#### `bicameral-integrations` owns

- Claude plugin package and manifest;
- compatibility declaration;
- Claude event-to-Bicameral boundary adaptation;
- calling the approved local/managed Bicameral endpoint;
- ephemeral plugin-local presentation state;
- Claude UI rendering;
- Claude commands such as `/bicameral-drift`;
- fallback text behavior on non-drawing surfaces;
- provider-specific validation/tests;
- provider-specific install metadata consumed by the Bicameral setup controller.

#### Claude Code owns

- host lifecycle events;
- host UI runtime;
- plugin loading/enabling/disabling;
- host permission model;
- plugin marketplace/install mechanics.

#### Bicameral installer/setup owns

- explicit installation consent;
- exact release-manifest binding;
- plan/apply/retry/reconciliation;
- supported-host detection;
- invocation of official host installation mechanisms;
- readiness projection;
- repair/uninstall mutation.

The installer consumes the Integrations-owned plugin artifact. Integrations does not create a second installer.

## Product invariant

The canonical statement for this integration is:

> **Bot detects drift. MCP/API exposes it. Integrations adapts it. Claude displays it. Humans and the existing daemon authority decide canonical change.**

## Managed MCP contract consumption

The plugin must consume the current accepted Managed MCP design rather than creating a Claude-specific truth model.

At minimum, preserve the semantics of:

- `ManagedPlanningBoundaryV1`;
- exact `plan_digest`;
- exact governing-spec repository/revision/path/blob/content identity;
- `CandidateSetV1` identities/generation/digest;
- source spans;
- proposed effects;
- contradiction references;
- dependency relationships;
- searched scope / coverage limitations;
- `MCPDisplayContractV1` presentation-state distinctions;
- allowed next operations;
- session lease/expiry behavior;
- exact preview before confirmation;
- explicit human confirmation before canonical mutation.

If accepted Bot/MCP implementation has evolved beyond the named July contracts, implementation MUST reconcile to current accepted code/contracts. This ADR freezes ownership and invariants, not stale field names.

## Planning-boundary trigger

The plugin must not infer a completed Planning boundary from assistant prose.

Current Claude Mod documentation exposes general events such as turns, commands, tools, prompts, sessions, and UI renders, but no provider-stable `PlanningComplete` event by that literal name.

Use this trigger preference order:

1. **Authoritative Bicameral signal.** Consume the existing Managed MCP/developer-host planning-boundary signal or an accepted successor that carries exact plan/spec/session identity.
2. **Version-proven Claude mapping.** Use a documented Claude event plus verifiable session state only if exact supported-version tests prove that mapping corresponds to the Bicameral planning boundary.
3. **Explicit command fallback.** Expose `/bicameral-drift` when automatic triggering cannot be proven.

For an unsupported/new Claude version, disabling auto-trigger and falling back to explicit review is preferable to guessing.

Forbidden trigger sources include:

- assistant prose pattern matching;
- a phrase such as "plan complete";
- latest filename or branch guessing;
- filesystem modification time;
- conversation summaries;
- current working directory alone.

## Presentation model

The plugin should default to compact attention, then progressive disclosure.

Example compact states:

```text
Bicameral · Design Drift: clear in searched scope
Bicameral · Design Drift: 3 proposed · 1 contradiction
Bicameral · Design Drift: incomplete
Bicameral · Design Drift: stale, refresh required
Bicameral · Design Drift: unavailable
```

The detailed view preserves upstream source identity and display semantics. It may improve layout, navigation, and accessibility, but it may not substitute a generated summary for the exact source of truth.

### Required state distinctions

At minimum preserve independently:

- analyzing;
- candidate set available;
- contradiction-bearing candidate result;
- no candidate within searched scope;
- partial/incomplete analysis;
- stale governing source;
- stale CandidateSet/generation;
- timeout;
- Bicameral unavailable/disconnected;
- unsupported protocol/version;
- session expired;
- malformed/contradictory response.

`no candidate within searched scope` is not `globally aligned`.

`unavailable` is not `clean`.

`stale` is not `current`.

## V1 interaction authority

V1 is intentionally conservative.

The plugin MAY:

- observe supported Claude lifecycle/session facts needed for the integration;
- receive an authoritative Bicameral planning boundary;
- call one approved Bicameral local/managed endpoint;
- retain bounded ephemeral display state;
- render status/detail UI;
- provide explicit read/review commands;
- expose existing governed prepare/review operations only when the user explicitly requests them and Bicameral authorizes them.

The plugin MUST NOT:

- approve Claude tool calls;
- bypass Claude user/org permission rules;
- intercept implementation tools to enforce plugin-local policy;
- rewrite user prompts;
- rewrite Claude tool arguments;
- run arbitrary shell commands;
- read unrelated environment secrets/settings;
- accept arbitrary network targets from prompt/session content;
- directly mutate canonical Product/Decision state;
- autonomously promote/reject/approve candidates;
- treat local session state as canonical Bicameral evidence;
- make compliance, merge, release, deployment, or global-safety claims from Design Drift.

A later ADR may deliberately expand interaction behavior. V1 does not reserve that authority by implication.

## Security decision

Anthropic explicitly documents that Mods run with the user's permissions and are not sandboxed. Therefore provider capability availability is not permission to use it.

The Bicameral plugin follows least capability:

```text
available host authority > plugin-declared authority > action actually needed
```

The package descriptor and review evidence should declare:

- Mod events handled;
- Mod API calls used;
- network destination class;
- filesystem access, ideally none beyond package/runtime necessities;
- process execution, expected none for v1;
- tool-approval capability, prohibited for v1;
- prompt/tool rewrite capability, prohibited for v1;
- canonical mutation capability, none.

`claude plugin validate` is required provider-side package validation but is not sufficient Bicameral security acceptance.

Disabling, blocking, or uninstalling the plugin must never weaken daemon-side governance. The plugin is a convenience/visibility surface over existing authority, not a security boundary.

## Installation decision

A Mod installs as a normal Claude plugin. The production path should therefore use Claude's supported plugin marketplace/install mechanisms rather than hand-writing Claude internals from this repository.

Conceptual product flow:

```text
Bicameral release manifest
  -> exact Claude plugin version + digest/source identity
  -> Bot setup reconciliation plan
  -> explicit operator consent
  -> official Claude plugin installation mechanism
  -> installed identity verification
  -> host reload/restart if required
  -> plugin compatibility/readiness projection
```

The exact marketplace/source shape remains implementation work under #315 because it must be tested against current Claude behavior and Bicameral release distribution architecture.

Important state distinctions:

```text
installed != loaded
loaded != enabled
loaded/enabled != Bicameral connected
connected != preflight completed
preflight completed != candidate available
candidate available != accepted Product change
```

User- or organization-disabled Mod state must be reported, not bypassed.

## Surface support decision

Current provider documentation says Mod drawing appears in interactive terminal and supported Claude Desktop Code surfaces, while hooks can run in additional environments where custom drawing is unavailable.

Therefore:

- interactive terminal is the initial required visual acceptance surface;
- supported Desktop Code is a secondary qualification target;
- VS Code chat/headless surfaces require a truthful text/command fallback when hooks load but drawing does not appear;
- no one surface's evidence may be generalized to all Claude surfaces.

## Compatibility and versioning

The plugin must declare at least:

- plugin version;
- minimum Claude Code version;
- exact Claude versions used for acceptance;
- required Bicameral protocol/capability version(s);
- supported display surfaces;
- required Mod events/API calls;
- package/source/digest identity once released.

A newer, untested Claude version may be permitted only according to an explicit compatibility policy. It must not be silently assumed equivalent if lifecycle/UI semantics used by Bicameral have changed.

## Repository structure

Initial target:

```text
plugins/
├── README.md
└── claude-code/
    └── design-drift/
        ├── .claude-plugin/
        │   └── plugin.json
        ├── hooks/
        │   ├── hooks.json
        │   └── register.ts
        ├── src/
        │   ├── drift-client.ts
        │   ├── planning-boundary.ts
        │   ├── presentation-model.ts
        │   └── render.ts
        ├── tests/
        └── README.md
```

Exact implementation language/build layout may vary with current Claude plugin constraints, but the ownership split remains.

## Parallel delivery

The plugin program runs in parallel with the installable Bicameral application work.

Independent lanes:

```text
Lane A: package + compatibility (#312)
Lane B: host-neutral drift client (#313)
Lane C: lifecycle + UX with fixtures (#314)

Convergence:
A + B + C -> exact plugin candidate
             |
             v
Lane D: managed install composition (#315)
             |
             v
Lane E: real Claude terminal/security acceptance (#316)
```

The core Bicameral installer/application must not be blocked by plugin progress unless a future release explicitly makes the plugin mandatory.

## Consequences

### Positive

- Drift awareness appears where planning and implementation happen.
- Bicameral reuses an already-designed capability instead of inventing a new governance subsystem.
- Claude-specific complexity stays out of Bot.
- Bot/MCP remain portable to Codex and future hosts.
- Integrations gains a clear location for installable host-runtime packages without overloading `mods/`.
- Plugin and installer can be developed concurrently with a narrow convergence contract.
- Disabling the plugin does not weaken core governance.

### Costs

- We must maintain compatibility against a provider-owned in-process API that can evolve.
- Security review must treat the plugin as privileged local code.
- Visual behavior differs across Claude surfaces.
- Automatic Planning trigger requires careful versioned integration rather than a convenient generic event name.
- Package distribution/version binding must be integrated into Bicameral's release/install story.

## Alternatives considered

### Put the Claude Mod in `bicameral-bot`

Rejected. Bot owns the capability semantics and canonical state, not every host-specific package. Putting provider UI/lifecycle code in Bot would couple the core to Claude and turn Bot into a host-adapter collection.

### Put the Claude Mod under existing `mods/`

Rejected. `mods/` already has a Bicameral-specific meaning: EM-safe advisory evidence processors. Anthropic Mods are executable host plugins with a different runtime, privilege model, and lifecycle. Same noun, different thing.

### Create a dedicated repository

Rejected for v1. Design Drift is not an independent product or authority service. It has one host, one narrow capability, and no reason to own a separate release/governance universe yet.

### Treat it as only another MCP tool/API

Rejected as the complete solution. MCP/API remains the correct backend capability boundary, but it cannot provide the in-process prompt-adjacent/pane UI and lifecycle behavior that makes the Claude Mod useful. The Mod should call the API, not replace it.

### Use only a settings hook

Possible fallback, but not selected as the primary experience. A settings hook can call external scripts/HTTP and react to lifecycle events, but it cannot provide the same interactive in-process UI/state/command experience. If the Mod API proves unstable for a required path, this alternative may be revisited without changing Bot semantics.

### Recalculate drift locally in the plugin

Rejected. It creates a second semantic engine and can diverge from canonical Bicameral Product state.

## Acceptance for this ADR

This ADR is accepted when maintainers agree that:

- `bicameral-integrations` owns the Claude package/presentation boundary;
- `plugins/` is the right packaging category;
- existing `mods/` semantics remain unchanged;
- Bot/MCP remain authoritative for drift semantics and canonical state;
- V1 is advisory and least-capability;
- installation composes through existing Bicameral setup rather than a second installer;
- automatic planning trigger must be authoritative/version-proven, never prose-inferred;
- terminal acceptance must use a real Claude Code build and real Bicameral path.

Implementation acceptance remains owned by #311 and children, not by ADR merge alone.