# Implementation Plan: Claude Code Design Drift plugin

**Date:** 2026-10-03  
**Status:** Implementation-ready plan  
**Program:** #311  
**ADR:** `docs/adr/0021-claude-code-plugin-design-drift-boundary.md`  
**PRD:** `docs/prd/claude-code-design-drift-plugin.md`

## 1. Goal

Build the smallest Claude-native surface that reliably exposes Bicameral's existing Managed MCP design-plan drift analysis immediately after a valid planning boundary, without moving semantic or canonical authority into Claude Code.

The implementation should proceed in parallel with the broader Bicameral installation/application work and converge only at the managed installation/release-manifest seam.

## 2. Architecture

```text
┌───────────────────────────────────────────────┐
│ Claude Code                                   │
│                                               │
│  Bicameral Design Drift plugin                │
│  ┌─────────────────────────────────────────┐  │
│  │ Claude lifecycle adapter                │  │
│  │ presentation state                      │  │
│  │ /bicameral-drift                        │  │
│  │ UI renderer / text fallback             │  │
│  └───────────────────────┬─────────────────┘  │
└──────────────────────────┼────────────────────┘
                           │ trusted local call
                           v
┌───────────────────────────────────────────────┐
│ Host-neutral DriftClient                      │
│                                               │
│  exact planning/spec/session identity         │
│  protocol/version validation                  │
│  state normalization without reinterpretation │
└──────────────────────────┬────────────────────┘
                           │ existing capability
                           v
┌───────────────────────────────────────────────┐
│ Bicameral MCP / local daemon                  │
└──────────────────────────┬────────────────────┘
                           v
┌───────────────────────────────────────────────┐
│ bicameral-bot                                 │
│ Managed MCP drift-aware continuation          │
│ Product / Candidate / Decision authority      │
└───────────────────────────────────────────────┘
```

No semantic arrow points back upward from Claude into Product authority except through an already-governed explicit Bicameral operation.

## 3. Target repository layout

```text
plugins/
├── README.md
├── _schema/
│   └── plugin-integration-descriptor.schema.json
├── index.json
└── claude-code/
    └── design-drift/
        ├── .claude-plugin/
        │   └── plugin.json
        ├── hooks/
        │   ├── hooks.json
        │   └── register.ts
        ├── src/
        │   ├── config.ts
        │   ├── compatibility.ts
        │   ├── planning-boundary.ts
        │   ├── drift-client.ts
        │   ├── presentation-model.ts
        │   ├── state.ts
        │   ├── render.ts
        │   ├── commands.ts
        │   └── diagnostics.ts
        ├── fixtures/
        │   ├── candidate.json
        │   ├── contradiction.json
        │   ├── bounded-clear.json
        │   ├── incomplete.json
        │   ├── timeout.json
        │   ├── unavailable.json
        │   ├── stale.json
        │   └── unsupported-version.json
        ├── tests/
        │   ├── compatibility.test.ts
        │   ├── planning-boundary.test.ts
        │   ├── drift-client.test.ts
        │   ├── presentation-model.test.ts
        │   ├── render.test.ts
        │   └── security-boundary.test.ts
        ├── integration.json
        ├── package.json
        └── README.md
```

Exact build tooling should follow the current Claude plugin examples and Bicameral repository conventions discovered at implementation time. Do not create Node dependency sprawl merely because TypeScript exists.

## 4. Package contract

### 4.1 Claude manifest

Use the provider-required `.claude-plugin/plugin.json` and `hooks/hooks.json` structures.

The provider manifest is necessary but not sufficient for Bicameral.

### 4.2 Bicameral integration descriptor

Add a provider-neutral enough descriptor for install/release/readiness tooling.

Illustrative shape:

```json
{
  "schema_version": 1,
  "id": "claude-code.design-drift",
  "name": "Bicameral Design Drift",
  "version": "0.1.0",
  "category": "host-plugin",
  "host": {
    "kind": "claude-code",
    "minimum_version": "2.1.287",
    "tested_versions": []
  },
  "bicameral": {
    "capability": "managed-mcp.design-drift",
    "protocol_versions": [],
    "canonical_state_mutation": false,
    "promotion_authority": "none"
  },
  "mod": {
    "events": [],
    "calls": [],
    "custom_ui": true,
    "text_fallback": true,
    "tool_approval": false,
    "prompt_rewrite": false,
    "tool_rewrite": false,
    "process_execution": false
  },
  "network": {
    "policy": "trusted-bicameral-endpoint-only"
  }
}
```

Do not populate `tested_versions` or protocol versions until actual evidence exists.

### 4.3 Index

`plugins/index.json` should aggregate plugin descriptors similarly to existing connector/mod indexes, allowing Bot/setup/UI tooling to discover package facts without scanning arbitrary files.

## 5. Core TypeScript boundaries

The exact type names may change, but keep these separations.

### 5.1 `PlanningBoundary`

A local representation of an upstream-authoritative boundary, not a Claude-derived guess.

Required identity should map to the accepted Managed MCP contract:

```ts
interface PlanningBoundary {
  productId: string
  hostKind: 'claude_code'
  hostSessionId: string
  hostTurnId: string
  planDigest: string
  governingSpec: {
    repositoryId: string
    gitHead: string
    artifactPath: string
    blobId: string
    contentDigest: string
  }
}
```

If the live upstream contract differs, adapt this interface to current accepted authority rather than maintaining a historical fork.

### 5.2 `DriftClient`

```ts
interface DriftClient {
  analyze(boundary: PlanningBoundary, signal?: AbortSignal): Promise<DriftResult>
  getCurrent?(sessionId: string): Promise<DriftResult | null>
}
```

The client handles:

- trusted endpoint resolution;
- transport/version negotiation;
- timeout/cancellation;
- response structural validation;
- exact request/response identity checks;
- no semantic inference.

### 5.3 `DriftResult`

Use a discriminated union so unknown/degraded cases cannot accidentally fall into a green boolean.

```ts
type DriftResult =
  | { kind: 'candidate'; source: SourceBinding; candidateSet: CandidateSetView }
  | { kind: 'bounded-clear'; source: SourceBinding; searchedScope: SearchedScope; limitations: Limitation[] }
  | { kind: 'incomplete'; source?: SourceBinding; limitations: Limitation[] }
  | { kind: 'stale'; reason: string; expected?: Identity; observed?: Identity }
  | { kind: 'timeout'; searchedScope?: SearchedScope; limitations: Limitation[] }
  | { kind: 'unavailable'; reasonCode: string }
  | { kind: 'unsupported'; reasonCode: string; observedVersion?: string }
  | { kind: 'expired'; reasonCode: string }
  | { kind: 'error'; reasonCode: string }
```

Do not introduce `aligned: boolean`.

### 5.4 `PresentationState`

Separate transport/model state from what the user sees.

```ts
type PresentationState = {
  generationKey: string | null
  status: 'idle' | 'analyzing' | 'candidate' | 'bounded-clear' | 'incomplete' |
          'stale' | 'timeout' | 'unavailable' | 'unsupported' | 'expired' | 'error'
  summary: string
  result?: DriftResult
  lastUpdatedAt?: number
}
```

Ephemeral only. Do not persist CandidateSets as canonical plugin state.

## 6. Trigger adapter

This is the highest-risk integration assumption and should be isolated behind one module.

### 6.1 Interface

```ts
interface PlanningBoundarySource {
  start(onBoundary: (boundary: PlanningBoundary) => void): Dispose
}
```

### 6.2 Preference order

1. Existing Bicameral host/MCP planning-boundary signal with exact identities.
2. Claude event/session mapping proven for the pinned/tested Claude version.
3. Manual `/bicameral-drift` command.

### 6.3 Version gate

Before enabling automatic triggering:

```text
Claude version supported?
  no -> command-only/degraded
  yes -> required event/session semantics available?
            no -> command-only/degraded
            yes -> automatic trigger enabled
```

### 6.4 Idempotency key

Use an identity derived from the authoritative boundary, for example:

```text
product_id + host_session_id + host_turn_id + plan_digest + spec_content_digest
```

Use exact upstream stable identity if one exists rather than inventing a parallel digest.

### 6.5 Race handling

- A later generation supersedes older in-flight requests.
- Abort older request where safe.
- An older response cannot write presentation state after a newer generation becomes current.
- Re-render/reconnect does not re-run analysis unless the authoritative upstream says refresh is required.

## 7. Claude Mod event strategy

At implementation time, re-read current official Mod reference and record the exact version.

Likely classes of hooks:

- session lifecycle to initialize/dispose plugin-local state;
- turn lifecycle to support a proven planning-boundary mapping only if necessary;
- command registration for `/bicameral-drift`;
- UI render hooks for compact/pane presentation;
- possibly session metadata access for non-authoritative routing context.

Do not register `tool.check`/permission-approval behavior for v1 unless the provider requires a read-only observation hook and security review explicitly accepts it. Design Drift does not need permission authority.

Do not register prompt/tool rewrite behavior for v1.

After implementation, `claude plugin validate` output should be treated as an auditable declaration and checked against `integration.json`.

## 8. UI design

### 8.1 Compact surface

Preferred: a small band/status near the prompt if provider UI API permits it without disturbing Claude's native interaction.

States:

```text
Bicameral · Design Drift: analyzing
Bicameral · Design Drift: clear in searched scope
Bicameral · Design Drift: 3 proposed · 1 contradiction
Bicameral · Design Drift: incomplete
Bicameral · Design Drift: stale
Bicameral · Design Drift: unavailable
```

### 8.2 Detail surface

Preferred: a pane or provider-native expandable presentation.

Information hierarchy:

1. Advisory label and result class.
2. Exact governing source identity.
3. Candidate/contradiction count.
4. Candidate effects and dependency state.
5. Source spans/references.
6. Coverage limitations/unknowns.
7. Exact next operation.
8. Diagnostic/protocol detail under progressive disclosure.

### 8.3 Text fallback

When drawing is unavailable:

- `/bicameral-drift` prints the same semantic state in bounded text;
- automatic hook may emit a concise transcript-safe notice if provider APIs support it without polluting the prompt/model context incorrectly;
- otherwise report that automatic display is unsupported and keep command access.

Do not silently claim the UI is active merely because hooks loaded.

## 9. Network and endpoint resolution

### 9.1 Trust source

Endpoint information comes from Bicameral-managed local setup/configuration, not Claude conversation content.

### 9.2 Allowed destination

V1 should call only the approved local/managed Bicameral endpoint class. Prefer loopback/local IPC where the current architecture permits it.

If a hosted endpoint is required, reuse existing authenticated Bicameral client/session configuration rather than introducing a plugin-owned secret.

### 9.3 Forbidden

- prompt-provided URL;
- arbitrary redirect following to untrusted hosts;
- plugin-owned long-lived API secret when an existing Bicameral session/transport is available;
- raw secrets in diagnostics.

## 10. Transport selection spike

Before implementing `DriftClient`, inspect current Bot/MCP production code and choose the smallest accepted transport.

Decision matrix:

| Option | Prefer when | Reject when |
|---|---|---|
| Existing MCP tool | already exposes exact Managed MCP result and can be invoked cleanly from Mod | requires Claude model/tool mediation for an internal plugin request or loses exact host/session identity |
| Local daemon API | already exposes exact result with authenticated local boundary | would create a plugin-only semantic endpoint or duplicate MCP behavior |
| Thin local adapter over MCP | needed to make Mod request deterministic without involving model/tool selection | becomes a second state engine or long-lived authority service |

The chosen path must be documented in #313 with current source references.

## 11. Install composition

### 11.1 Release artifact

Integrations produces an exact plugin package/source identity.

Possible distribution forms to evaluate under #315:

- Bicameral-controlled Claude plugin marketplace repository;
- versioned subdirectory/source in a release-bound repository;
- another official Claude-supported marketplace source with immutable revision binding.

Do not use a mutable local clone as the production artifact merely because `--plugin-dir` is convenient for development.

### 11.2 Setup controller handoff

Integrations exposes facts. Bot/setup executes mutation.

```text
Integrations artifact metadata
  -> Bot release manifest
  -> setup plan
  -> operator consent
  -> official Claude plugin install/update/disable/uninstall mechanism
  -> verify exact plugin identity
  -> readiness projection
```

### 11.3 No second installer

No `install.sh`, curl-pipe-shell, arbitrary PowerShell, or manual Claude settings mutation should become the normal plugin install path.

## 12. Readiness model

Do not create one `ready` boolean.

Recommended facts for setup/readiness projection:

```text
host_version_supported
plugin_package_present
plugin_version_matches
plugin_enabled_state
plugin_loaded_state_if_observable
bicameral_connection_state
auto_trigger_supported
custom_ui_supported
text_fallback_supported
last_validation_result
```

Setup owner decides how these map into existing readiness contracts.

## 13. Security implementation checklist

### Source review

- [ ] No `tool.check` allow/approve path.
- [ ] No prompt rewrite.
- [ ] No tool argument rewrite.
- [ ] No arbitrary `child_process`/process execution.
- [ ] No environment enumeration.
- [ ] No generic filesystem traversal.
- [ ] No prompt-controlled network destination.
- [ ] No direct Product/Decision store writes.
- [ ] No autonomous prepare-confirm chain.

### Identity

- [ ] planning boundary exact identity checked;
- [ ] spec content/revision checked;
- [ ] response generation/currentness checked;
- [ ] old result cannot overwrite new generation;
- [ ] session-expired data discarded.

### Presentation

- [ ] hostile source text remains display data;
- [ ] source text is not evaluated as code/config;
- [ ] color is supplemental;
- [ ] malformed content bounded before render;
- [ ] error text redacted.

### Installation

- [ ] exact version/digest bound;
- [ ] provider minimum version checked;
- [ ] organization-disabled state respected;
- [ ] unrelated configuration preserved;
- [ ] no floating automatic update during active session unless separately governed.

## 14. Test pyramid

### Unit

- compatibility/version selection;
- request/response validation;
- discriminated result mapping;
- presentation strings;
- generation/idempotency logic;
- redaction.

### Contract

- frozen upstream Managed MCP fixtures;
- future-version rejection;
- spec/candidate identity mismatch;
- provider plugin descriptor validation.

### Mod harness

- hook registration;
- command behavior;
- UI rendering states;
- drawing-unavailable fallback;
- lifecycle cleanup.

### Real-process component

- actual local daemon/MCP request;
- real Claude plugin validation;
- real disposable Claude plugin install/update/uninstall.

### Terminal user journey

Owned by #316:

- real supported Claude build;
- exact plugin artifact;
- real Bicameral candidate;
- real planning boundary;
- automatic preflight;
- candidate/no-candidate/adverse states;
- restart/disable/repair/uninstall;
- adversarial security review.

## 15. CI gates

Add only gates that protect actual product risk.

Recommended:

1. schema/descriptor validation;
2. TypeScript/lint/test as chosen by package tooling;
3. package-content allowlist or inspection;
4. static assertion that prohibited Mod capabilities are absent where mechanically testable;
5. fixture contract tests;
6. `claude plugin validate` in an environment with a pinned supported Claude version if licensing/distribution permits CI execution;
7. dependency/SAST policy consistent with repository governance.

Do not claim real Claude user-journey acceptance from CI simulation.

## 16. Delivery tranches

### Tranche A: package and taxonomy (#312)

Can start immediately.

Deliver:

- `plugins/` structure;
- provider manifest skeleton;
- Bicameral integration descriptor/schema/index;
- version compatibility policy;
- provider validation;
- package README.

Exit: installable skeleton with no false semantic claims.

### Tranche B: DriftClient (#313)

Can start immediately in parallel with A.

Deliver:

- current upstream contract reconciliation;
- transport decision;
- discriminated result model;
- response identity validation;
- fixtures/adversarial tests.

Exit: host-neutral code can faithfully retrieve/map a real or reference Managed MCP result.

### Tranche C: Claude UX (#314)

Can begin against fixtures in parallel with A/B.

Deliver:

- command;
- compact states;
- detail renderer;
- fallback renderer;
- lifecycle adapter;
- auto-trigger compatibility gate;
- accessibility tests.

Exit: real provider package can render every semantic state, with automatic trigger enabled only where proven.

### Tranche D: install composition (#315)

Starts after exact package identity exists; research can start earlier.

Deliver:

- marketplace/source decision;
- release artifact/digest;
- setup-consumable metadata;
- install/update/repair/uninstall test evidence;
- readiness mapping proposal to Bot setup owner.

Exit: Bot installer can bind and manage one exact plugin candidate through supported provider tooling.

### Tranche E: terminal acceptance (#316)

Starts after A-D converge.

Deliver:

- clean/disposable Claude environment;
- exact version matrix;
- real Bicameral integration;
- adverse-state matrix;
- security review;
- operator journey evidence.

Exit: program #311 can close.

## 17. Parallel work assignment

The program is intentionally decomposed so different developers/agents can work without stomping the same files.

Suggested ownership boundaries:

```text
Worker A: plugins/_schema + integration descriptor + package manifest
Worker B: src/drift-client + upstream contract fixtures
Worker C: src/render + commands + UI fixtures
Worker D: install/distribution research + Bot setup contract proposal
Reviewer: security/adversarial review across converged candidate
```

Avoid multiple workers editing the root plugin registration module simultaneously until their seams are stable.

## 18. Cross-repository coordination points

### Bot

Potential required follow-up only if current code lacks a clean plugin-consumable seam:

- expose/reuse exact planning-boundary identity;
- expose/read existing Managed MCP result through accepted local API;
- add release-manifest plugin binding;
- extend setup/readiness facts.

Do not move Claude rendering code into Bot.

### MCP

Potential required follow-up only if current transport lacks a deterministic plugin client path:

- exact request/response capability;
- session/boundary identifiers;
- compatibility/version declaration.

Do not move provider-specific Claude UI into MCP.

### Factory/release governance

Once implementation begins, normal Bicameral product governance determines release-unit/admission evidence. This design document does not grant merge/release authority.

## 19. Evidence expected on implementation PRs

Each implementation PR should state:

- issue/tranche;
- exact Claude Code version used;
- exact upstream Bot/MCP contract/revision used;
- Mod events registered;
- Mod API calls used;
- network behavior;
- canonical-state mutation capability = none or explicitly justified by later authority;
- tests run;
- rendered evidence if UI changed;
- known unsupported/degraded surfaces;
- state refinement: what new durable state, if any, was added (expected none in Integrations v1).

## 20. Stop conditions

Pause and route architecture review if implementation discovers any of these:

- automatic planning trigger requires parsing Claude prose;
- current MCP/API cannot preserve exact planning/spec identity;
- plugin must approve or intercept tools to deliver basic visibility;
- plugin needs a long-lived secret not already governed by Bicameral setup;
- plugin needs its own canonical CandidateSet store;
- installation requires unsupported direct mutation of Claude internals;
- provider Mod API behavior differs materially from the assumptions in ADR-0021;
- v1 cannot fail visibly on disabled/unsupported/degraded states.

These are architecture signals, not invitations to make the plugin more magical until tests stop complaining.