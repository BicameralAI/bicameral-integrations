# PRD: Bicameral Claude Code Design Drift plugin

**Date:** 2026-10-03  
**Status:** Proposed  
**Program:** #311  
**Architecture:** ADR-0021  
**Product dependency:** `BicameralAI/bicameral-bot#979` Managed MCP drift-aware continuation

## 1. Product summary

Bicameral Claude Code Design Drift is a small installable Claude Code plugin that surfaces Bicameral's existing Managed MCP design-plan drift analysis directly inside the developer's Claude Code session.

The product promise is:

> **See when Claude's implementation plan has drifted from the accepted Bicameral design before implementation starts.**

The plugin does not create a new drift engine. It is a Claude-native client and presentation surface over the existing Bicameral Bot/MCP capability.

## 2. Problem

AI-assisted development compresses the time between intent, planning, and implementation. A developer can ask Claude to plan a change and move directly into edits before noticing that the plan:

- conflicts with an accepted Product decision;
- collapses an important state distinction;
- assumes a happy path where the design requires branching behavior;
- generalizes host-specific behavior incorrectly;
- omits authority, evidence, or transition requirements;
- relies on stale or incomplete Product context.

Bicameral already has a drift-aware Managed MCP preflight designed for this moment. The remaining product gap is presentation and timing: make the result visible in Claude Code without requiring the developer to remember a separate command, dashboard, or governance ritual.

## 3. Product principles

### 3.1 Invisible until useful

The plugin should not turn every planning turn into a wall of governance text. Default presentation is a compact state indicator. Detail appears when there is something to review or the user explicitly opens it.

### 3.2 Advisory, not obstructive

V1 preflight does not block implementation. It informs the developer and preserves the existing Managed MCP authority model.

### 3.3 Exact source over generated confidence

When detail matters, show the exact bound governing source and exact candidate/contradiction information from Bicameral. A convenient LLM summary may explain, but it cannot replace the source of truth.

### 3.4 Unknown stays unknown

Unavailable, stale, incomplete, timeout, and unsupported states must never render as aligned/clean.

### 3.5 Host convenience never becomes Product authority

Claude Code is a client. The plugin is a client. Bicameral remains authoritative for Product state and governed mutation.

### 3.6 No duplicate architecture

The feature should make existing Managed MCP capability easier to use, not recreate the same capability inside Integrations.

## 4. Target users

### Primary

A developer using Claude Code to plan and implement work in a repository associated with a Bicameral Product.

### Secondary

- Product/engineering leads reviewing implementation direction from inside a coding session.
- Developers onboarding to an existing Product who need accepted design context surfaced at planning time.
- Bicameral evaluators testing the installable product in a realistic developer-host journey.

### Not a target for v1

- Organization administrators seeking a full control-plane UI.
- Release managers seeking release readiness or deployment control inside Claude.
- Users who do not use Claude Code. Bicameral baseline remains useful without this plugin.

## 5. Jobs to be done

### JTBD-1: Catch drift before code

When I finish planning implementation work in Claude, show me whether Bicameral found relevant differences or contradictions before I start editing.

### JTBD-2: Understand why

When drift is reported, let me inspect the exact accepted design passages, proposed effects, dependencies, contradictions, and limitations without leaving my coding session.

### JTBD-3: Trust negative results

When no candidate is found, tell me what scope was searched and what limitations remain so I do not mistake a bounded result for a global guarantee.

### JTBD-4: Recover from missing capability

When Bicameral is disconnected, stale, incompatible, or unavailable, tell me exactly what failed and what safe next action is available.

### JTBD-5: Continue governed review when needed

When I want to act on a candidate, route me into the existing Bicameral prepare/preview/confirmation path without giving the plugin or Claude autonomous authority.

## 6. User stories

1. As a developer, after a valid planning boundary I see Design Drift begin automatically without invoking a separate tool.
2. As a developer, if no actionable candidate is found I see `clear in searched scope`, not a global `aligned` claim.
3. As a developer, if candidates exist I see a concise count and can open exact detail.
4. As a developer, if a contradiction exists I can distinguish it from a normal proposal.
5. As a developer, if analysis is incomplete or times out I see that limitation rather than a green state.
6. As a developer, I can run `/bicameral-drift` to inspect or refresh the current result.
7. As a developer on a Claude surface without custom Mod drawing, I still receive a usable textual/command fallback.
8. As a developer, disabling the plugin removes the Claude convenience surface but does not alter Bicameral governance state.
9. As an operator, install/update/repair uses the normal Bicameral setup path and preserves my unrelated Claude configuration.
10. As a security reviewer, I can enumerate the Mod events/API calls/network behavior before approving the plugin.

## 7. Scope

### V1 required

- Installable Claude Code plugin containing a Mod.
- Versioned compatibility declaration.
- Automatic advisory preflight from an authoritative/version-proven planning boundary.
- Explicit `/bicameral-drift` command.
- Compact Design Drift status.
- Detailed source/candidate review.
- Candidate, contradiction, bounded no-candidate, partial/incomplete, stale, timeout, unavailable, incompatible, and session-expired states.
- Exact governing-spec identity and provenance.
- Textual fallback where custom Mod drawing does not appear.
- Real Claude Code terminal acceptance.
- Managed install/update/repair/uninstall composition with Bicameral setup.
- Security hardening proving least capability.

### V1 optional if low-risk

- One-click/open-pane transition from compact status to detailed view.
- Copy stable candidate/reference identity for troubleshooting.
- Explicit refresh action.
- Link/reference to a richer Bicameral application view if a stable deep-link contract exists.

### Deferred

- Blocking tool calls because drift exists.
- Automatic intervention before every edit.
- General Bicameral dashboard/control plane inside Claude.
- Cross-host shared plugin architecture beyond reusable host-neutral client logic.
- Organization-wide policy administration.
- Release readiness, deployment, compliance, or merge controls.
- Autonomous candidate promotion/rejection.
- New drift analysis semantics.

## 8. User experience

### 8.1 Happy path: no candidate

```text
Developer completes planning
  -> Bicameral · Design Drift: analyzing
  -> Bicameral · Design Drift: clear in searched scope
```

Expanding the result shows:

- exact governing spec identity/revision;
- searched scope;
- coverage/unknown limitations;
- timestamp/generation appropriate to the upstream result;
- next action: continue, refresh, or inspect source.

The wording `clear in searched scope` is required. Avoid `aligned`, `safe`, `approved`, or `no drift` unless the upstream contract explicitly earns a stronger claim.

### 8.2 Happy path: candidates

Compact:

```text
Bicameral · Design Drift: 3 proposed · 1 contradiction
```

Detailed review:

```text
Design Drift · advisory
Governing spec: <exact identity>
Candidate set: <stable generation>

1. <candidate effect>
   Source: <exact span/reference>
   Dependencies: ...
   Status: proposed

2. <candidate effect>
   Source: ...
   Status: contradiction

Coverage limitations: ...
Next: continue work, inspect, or begin governed review
```

Exact layout may evolve. Semantic fields may not.

### 8.3 Incomplete/timeout

Compact:

```text
Bicameral · Design Drift: incomplete
```

Detail explains:

- what completed;
- what did not;
- timeout/limitation type;
- searched scope if known;
- safe next action.

No false green result is shown.

### 8.4 Disconnected/unavailable

Compact:

```text
Bicameral · Design Drift: unavailable
```

Detail distinguishes, where evidence permits:

- Bicameral daemon unavailable;
- MCP/capability unavailable;
- Product/session not bound;
- plugin/Bicameral protocol incompatible;
- plugin disabled or blocked by organization policy;
- governing spec binding unavailable.

### 8.5 Stale

A stale result remains visible only if clearly marked stale and cannot overwrite a newer planning generation.

```text
Bicameral · Design Drift: stale, refresh required
```

### 8.6 Session expiry

Session-scoped candidate data must be removed/invalidated according to the upstream Managed MCP session contract. The plugin may show that review state expired; it must not resurrect candidates from its own cache.

## 9. Command behavior

### `/bicameral-drift`

Required command. It should:

- show current result if still current;
- trigger a supported refresh when the current authoritative planning boundary permits it;
- explain when no planning boundary is available;
- never fabricate a governing source;
- never directly mutate Product state.

Potential future commands require separate acceptance if they perform consequence-bearing actions.

## 10. Automatic trigger behavior

Current Claude Mod API does not document a literal `PlanningComplete` event. Automatic trigger implementation is therefore a compatibility feature, not an assumption.

Requirements:

1. Prefer an authoritative Bicameral planning-boundary signal already produced by Managed MCP/host integration.
2. A Claude lifecycle-event mapping is acceptable only when tested against an exact supported Claude build and when it preserves the required Bicameral boundary identity.
3. Never parse assistant prose to infer planning completion.
4. Fire once per exact planning-boundary generation.
5. Reconnect/re-render must not create duplicate analysis.
6. A new planning generation supersedes older display state.
7. If auto-trigger compatibility is unknown, fall back to `/bicameral-drift` and report the limitation.

## 11. Functional requirements

### FR-1 Package

The feature ships as a valid Claude Code plugin/Mod package.

### FR-2 Compatibility

The package declares minimum and tested Claude Code versions and required Bicameral capability/protocol versions.

### FR-3 Connection

The plugin reaches Bicameral only through a trusted configured endpoint/path established by Bicameral setup. Prompt/session data cannot select arbitrary outbound destinations.

### FR-4 Planning identity

The plugin submits or references the exact authoritative planning boundary required by Managed MCP.

### FR-5 Drift retrieval

The plugin consumes an existing Bicameral drift result. It does not calculate semantic alignment independently.

### FR-6 State fidelity

Every upstream result/degraded state required by ADR-0021 remains distinguishable in the presentation model.

### FR-7 Source fidelity

Exact source identity/spans survive into detailed review.

### FR-8 Compact UX

The default state is concise and attention-oriented.

### FR-9 Detailed UX

The user can inspect enough exact detail to understand the candidate/contradiction/limitation.

### FR-10 Fallback

A non-drawing host surface has a textual/command path rather than silent loss of function.

### FR-11 Advisory posture

Drift existence alone does not block tools or implementation in v1.

### FR-12 Governed action

Any action that changes canonical Bicameral state routes through existing daemon authority and explicit confirmation.

### FR-13 Install lifecycle

The plugin can be installed, updated, repaired, disabled, and uninstalled without editing unrelated Claude configuration.

### FR-14 Diagnostics

Errors identify typed causes without exposing secrets or unnecessary local paths.

## 12. Non-functional requirements

### Reliability

- Same planning boundary is idempotent.
- Old responses cannot overwrite a new generation.
- Lost responses do not create duplicate canonical effects.
- Plugin restart/reload does not invent state.
- Unsupported protocol versions fail visibly.

### Performance

- Compact status should appear promptly when preflight begins.
- Rendering overhead should be small relative to Managed MCP analysis.
- Network/request cancellation must be bounded to session lifecycle.
- Provider-side UI work must not freeze the terminal.

The upstream Product policy currently starts at a 60-second Managed MCP analysis boundary. V1 should measure its own overhead separately rather than inventing a new semantic timeout.

### Accessibility

- No color-only meaning.
- Keyboard-operable interactive elements.
- Readable narrow-terminal behavior.
- Textual status labels.
- Progressive disclosure rather than mandatory full-spec dumps.

### Privacy

- Send only data required by the established Managed MCP contract.
- Do not collect unrelated Claude prompts/session content for telemetry.
- Do not read arbitrary environment variables/secrets.
- Do not emit local sensitive paths in remote/browser-visible diagnostics.

### Security

- No tool approval handler in v1.
- No prompt rewrite handler in v1.
- No tool-argument rewrite handler in v1.
- No arbitrary process execution.
- No direct canonical Product write.
- No autonomous promotion or approval.
- Bounded endpoint selection.
- Malformed/up-version data fails closed into an explicit unsupported/error state.

## 13. Host surface matrix

| Surface | Hooks | Custom Mod UI | V1 requirement |
|---|---|---|---|
| Claude Code interactive terminal | supported | supported | Required full experience |
| Claude Desktop Code tab | supported where provider allows | supported with provider limits | Secondary qualification |
| VS Code extension chat panel | hooks can run | custom drawing not shown | Text/command fallback, no silent success |
| `claude -p` / Agent SDK | hooks can run | no custom drawing | Compatibility observation; not primary UX |
| cloud/remote sessions | provider-dependent | provider-limited | Explicitly qualify before claiming support |

The exact table must be revalidated against current Anthropic documentation during release qualification.

## 14. Installation and distribution requirements

The Mod installs as a Claude plugin. Production distribution must use supported Claude plugin mechanisms.

Requirements:

- version-addressable plugin package/source;
- exact package identity/digest bindable by the Bicameral release manifest;
- no floating mutable source as the authoritative installed artifact;
- official Claude plugin validation;
- explicit Bicameral setup plan/consent;
- detected Claude version before activation;
- idempotent update/repair;
- preserve unrelated plugins/settings;
- typed disabled-by-user and disabled-by-organization states;
- uninstall only Bicameral-owned plugin state to the extent supported by provider tooling;
- clear reload/restart guidance when required by Claude.

## 15. Product states

Plugin-specific observed state should remain small and derived where possible.

Suggested presentation/readiness dimensions:

```text
package:
  absent | installed | version_mismatch | invalid

host:
  unsupported | compatible | reload_required | disabled_user | disabled_org

bicameral_connection:
  disconnected | available | degraded

planning:
  none | current | stale | expired

analysis:
  idle | analyzing | candidate | bounded_clear | incomplete | timeout | unavailable | unsupported | error
```

These are integration/readiness dimensions, not new Product lifecycle states.

## 16. Success measures

### Correctness measures

- 100% of rendered drift results retain exact upstream source/candidate generation identity in test/acceptance evidence.
- 0 known cases where unavailable/stale/incomplete state renders as clean/aligned.
- 0 autonomous canonical mutations from plugin code.
- 0 tool approvals or permission bypasses from v1 plugin code.
- No duplicate preflight for the same planning-boundary generation in acceptance scenarios.

### Experience measures

Record during dogfood/alpha:

- planning-boundary to first visible status latency;
- Managed MCP request latency;
- render latency separately;
- frequency of candidate, contradiction, bounded-clear, incomplete, timeout, and unavailable outcomes;
- percentage of candidate/contradiction results opened for detail;
- duplicate/noisy notification rate;
- number of manual steps needed to inspect exact source;
- rate of command fallback use because automatic UI/trigger was unavailable.

Do not set vanity adoption targets before dogfood data exists.

### Burden guardrail

The plugin fails the product goal if developers routinely disable it because it interrupts ordinary work despite being advisory.

## 17. Telemetry

V1 telemetry, if enabled by Bicameral policy, should be event-minimal and privacy-preserving.

Potential metrics:

- plugin loaded/version/surface class;
- auto-trigger attempted/succeeded/unsupported;
- result class only;
- latency buckets;
- detail opened;
- typed error/recovery code.

Do not collect:

- raw prompts;
- source code;
- exact governing spec content;
- candidate text;
- environment secrets;
- arbitrary session transcript.

Telemetry policy and transport must follow existing Bicameral rules. Absence of telemetry must not reduce functional correctness.

## 18. Rollout plan

### Phase 0: documentation and contract

- ADR-0021.
- PRD.
- implementation plan.
- issue program and children.

### Phase 1: skeleton + fixture UI

- valid plugin package;
- compatibility descriptor;
- `/bicameral-drift` command;
- UI/state matrix against fixtures;
- provider validation.

### Phase 2: real Bicameral client

- host-neutral drift client;
- exact source/generation fidelity;
- degraded-state handling;
- real development daemon/MCP path.

### Phase 3: automatic planning boundary

- authoritative/version-proven trigger;
- once-per-generation behavior;
- reconnect/supersession/session-expiry handling.

### Phase 4: managed install composition

- exact plugin artifact;
- release-manifest binding;
- setup plan/apply/repair/uninstall integration;
- version/disabled-state readiness.

### Phase 5: terminal acceptance

- real Claude Code profile;
- real Bicameral candidate;
- adversarial security review;
- terminal user-journey evidence.

## 19. Release acceptance

The feature is not shippable merely because the plugin validates or renders fixtures.

Release candidate requires:

- accepted ADR/PRD boundary;
- exact plugin artifact identity;
- supported Claude version matrix;
- real Managed MCP result path;
- authoritative/version-proven planning trigger or explicitly accepted command-only fallback;
- state/degraded matrix tests;
- least-capability security review;
- managed install/recovery evidence;
- real Claude terminal end-to-end evidence under #316;
- human review of the final authority/security posture.

## 20. Explicit non-goals

- Replacing Bicameral's application.
- Replacing Managed MCP.
- Recreating Product state in Claude.
- Blocking development on advisory drift.
- Autonomous promotion, rejection, approval, merge, release, or deployment.
- CodeGraph completeness claims.
- General compliance/safety claims.
- Making Claude Code a required Bicameral dependency.
- Solving every developer host in this program.

## 21. Open implementation questions

These are engineering decisions, not unresolved product authority:

1. Which current accepted Bicameral transport should the plugin call directly: MCP tool path, local daemon API, or a thin MCP-backed local endpoint?
2. What exact Claude event/session signal can be proven as the automatic trigger for the supported Claude version?
3. What is the smallest useful custom UI component: prompt band, pane, or a combination?
4. What immutable marketplace/package source best fits Bicameral release distribution?
5. Which plugin readiness facts should be added to the existing setup/readiness projection rather than creating a parallel state model?

These questions may change implementation. They do not change the architecture invariant that Claude adapts and presents while Bicameral owns semantics and authority.