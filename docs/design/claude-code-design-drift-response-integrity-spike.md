# Claude Code Design Drift: Product Routing and Response Integrity Spike

Status: remediation checkpoint for #319 after adversarial review  
Program: #311  
Client workstream: #313  
Upstream routing seam: BicameralAI/bicameral-mcp#871  
Live semantic provider dependency: BicameralAI/bicameral-bot#958 / #1066

## Purpose

This note freezes the architectural frame for the bounded Design Drift remediation slice before broader Claude UX, installer composition, Product routing, or candidate action flows proceed.

The work now separates five identities that must never be collapsed into one another:

1. Claude session identity;
2. Claude agent/thread identity;
3. provider workspace routing hints;
4. canonical Bicameral Product identity; and
5. exact Managed Planning / CandidateSet response identity.

The plugin remains a host adapter. It does not become a Product resolver, semantic drift engine, or authority service.

## Decision summary

### Main-thread only in v0.1

Anthropic hook events may include `agent_id` when the event fires inside a subagent. `ManagedPlanningBoundaryV1` currently has no agent-identity dimension.

Therefore v0.1 accepts `ExitPlanMode` only from the main Claude session thread. A planning event carrying `agent_id` is ignored and must not clear, replace, or supersede the main-thread Design Drift state.

This is a compatibility boundary, not a claim that subagent planning is unimportant. Supporting subagent planning later requires an explicit upstream identity contract rather than silently folding multiple agents into one host session.

### Stable session routing hint, not mutable cwd

Anthropic documents `cwd` as a common hook field that changes after directory/worktree changes. It is useful as a provider-authored routing hint but is not stable Product identity.

The plugin therefore captures `session.start.cwd` once as the session routing hint. Later `PostToolUse.cwd` values are ignored for Product routing.

That captured path is still only a hint. It is not sent anywhere until the host-neutral MCP resolution seam in #871 exists.

Intended future flow:

```text
Claude session.start
  capture provider-authored initial cwd once
        |
        | routing hint only
        v
bicameral.workspace.resolve        # proposed MCP seam, MCP #871
        |
        | daemon-owned LocalWorkspaceBinding lookup
        v
canonical product_id OR typed failure
        |
        v
bicameral.product.select(product_id)
        |
        | existing MCP session memory
        v
Product-scoped MCP tools
```

Forbidden Product recovery remains:

- current mutable cwd by itself;
- folder names;
- git remotes;
- CLAUDE.md or transcript content;
- model reasoning;
- environment guesses;
- first/nearest workspace binding;
- prior Product state from another process.

### Response integrity before semantic interpretation

A successful MCP call is not sufficient evidence that the returned result belongs to the current Plan.

The client binds every rendered result to the exact request identity and applies a bounded response envelope first:

```text
requested Managed Planning boundary
  host_kind
  host_session_id
  host_turn_id
  plan_digest
  optional product_id
        |
        v
bicameral.preflight
        |
        +-- ordinary managed_preflight payload
        |
        +-- additive managed_mcp_candidate_set payload
        v
bounded integrity layer
  content count / total JSON size bounded
  duplicate-equivalent payloads tolerated
  conflicting Managed Preflight payloads rejected
  conflicting CandidateSet payloads rejected
  success + error mixtures rejected
  authoritative enum values validated
  sha256 digests validated
  UUID candidate identities validated
        |
        v
exact identity validation
  returned boundary == requested boundary
  CandidateSet Product == returned/requested Product
  CandidateSet host session == requested host session
  CandidateSet plan digest == requested plan digest
  CandidateSet spec-binding digest == returned spec-binding digest
  contract version supported
  candidate identities unique
        |
        v
bounded presentation model
```

Any mismatch is an integrity failure, never a drift result.

## Provider facts

Canonical provider sources remain cataloged in:

- `plugins/claude-code/README.md`
- `plugins/claude-code/design-drift/references.md`

Relevant facts for this checkpoint:

- `classic.PostToolUse` is the settings-hook-compatible event bridge used for `ExitPlanMode`;
- hook events may identify subagent execution with `agent_id`;
- common hook `cwd` follows Claude after directory/worktree changes;
- Mods API calls can be intercepted by earlier Mods, so host-local display is advisory and not canonical evidence;
- command return text becomes Claude-visible conversational context and must remain bounded.

## Current Bicameral facts

### Product selection is MCP-process-local

`bicameral.product.select` retains one canonical Product for the current MCP stdio process only after daemon route validation.

Product-scoped tools return `product_context_required` when that state has not been established.

The existing legacy SessionStart hook is a separate process and therefore cannot populate this MCP process memory.

### workspace.resolve already exists below MCP

The current daemon command `workspace.resolve` is already consumed by the managed host prework runner. It resolves a host-provided candidate path against daemon-owned `LocalWorkspaceBinding` state and returns a Product routing fact or typed fail-closed outcome.

The missing seam is MCP exposure, tracked in BicameralAI/bicameral-mcp#871.

Integrations does not implement a substitute.

### preflight is multi-content

Current `bicameral.preflight` may return:

1. the ordinary managed preflight response; and
2. an additive `managed_mcp_candidate_set` / `MCPDisplayContractV1` surface when candidate working state exists.

A client that parses only the first JSON text block is incomplete. A client that accepts two conflicting copies is also incomplete.

## Implemented remediation behavior

The package now splits responsibilities explicitly:

- `provider.js` owns Claude-specific main-thread eligibility and session-start routing-hint capture;
- `drift.js` owns exact Plan hashing and host-neutral semantic/result mapping;
- `integrity.js` bounds and validates the MCP response before it becomes persistent Mod state or transcript-visible output;
- `register.js` owns lifecycle wiring, in-flight coalescing, background scheduling, fail-open presentation, and ephemeral state.

The implementation now:

- ignores subagent `ExitPlanMode` events without disturbing main-thread state;
- captures `session.start.cwd` once and does not use later mutable cwd values for routing;
- parses structured MCP content plus every JSON text result block;
- rejects conflicting Managed Preflight payloads;
- rejects conflicting CandidateSet payloads;
- rejects responses mixing typed errors with semantic success surfaces;
- bounds content item count and aggregate structured/text JSON size;
- validates authoritative Managed Preflight outcome/status/class enums against current Bot contracts;
- validates exact `sha256:<64 lowercase hex>` digests;
- validates CandidateSet and candidate UUID identities;
- caps candidate count before projection;
- preserves typed MCP errors;
- compares returned host kind, host session, host turn, and Plan digest against the exact request;
- checks CandidateSet Product, session, Plan, and spec-binding identity;
- keeps raw candidate/spec/limitation prose out of transcript-visible command text;
- coalesces refresh with identical scheduled/in-flight work;
- contains plugin/UI/scheduling failures so Design Drift cannot interrupt normal Claude execution.

## Security rationale

### Do not launder transport success into semantic success

A returned JSON object can still be stale, crossed, malformed, duplicated, conflicting, oversized, or bound to another Product/session/Plan.

Transport bounds and contract validation occur before semantic state mapping.

### Do not treat provider strings as harmless merely because they are short

Transcript-visible outcome/status/class values are accepted only from the current closed Bot enums. Digest and UUID fields must match exact formats. Unknown provider/MCP limitation codes are replaced with a bounded local `unrecognized_limitation_code` marker before command rendering.

This does not make the Mod chain trusted. It only prevents arbitrary prose from masquerading as typed Bicameral state.

### Do not turn command output into a prompt-injection bridge

Claude command return text becomes conversational context. Candidate text, governing-spec prose, provider limitation detail, and source excerpts remain untrusted content.

During this checkpoint, `/bicameral-drift` may show only bounded typed facts such as:

- locally selected state text;
- validated outcome/status classes;
- validated spec-binding digest;
- validated CandidateSet id/generation/count;
- bounded limitation codes.

Human-readable candidate/spec prose requires a separately reviewed human-only pane or another governed context-injection design.

### Do not create Product authority in the host

Workspace resolution is routing, not identity creation. CandidateSet state is transient working state, not canonical Product state. The plugin cannot promote, approve, or confirm anything in this slice.

## Known blockers and intentional non-solutions

### MCP Product-routing seam

Until MCP #871 exists, a fresh Claude plugin session may still receive `product_context_required`.

The plugin reports that state honestly. It does not infer or auto-invent Product context. The captured session routing hint remains dormant until the accepted MCP tool exists.

### Live ClaimTrace producer

Current Bot Managed Preflight treats absent `claim_trace` as provider unavailable. MCP does not produce a live trace itself.

Therefore normal semantic Design Drift remains activation-blocked on Bot #958 / #1066 or an accepted successor.

Integrations must not duplicate the semantic provider merely to make the UI look alive.

### Mod-chain trust

An earlier Claude Mod can still intercept or alter lifecycle/API traffic. This package is therefore a host-advisory presentation surface, not governance evidence. Stronger trust would require an accepted authenticated/request-bound receipt design or equivalent control outside the Mod chain.

## Required remediation evidence

Host-neutral Node-backed fixtures must prove:

- subagent Plan events are ineligible;
- stable routing hint comes from session start;
- exact Plan hashing and tool-use fallback;
- no transcript recovery when exact Plan bytes are missing;
- contradiction / timeout / unclassified states remain distinct;
- multi-content response preserves CandidateSet metadata;
- conflicting Managed Preflight payloads fail closed;
- conflicting CandidateSet payloads fail closed;
- returned Plan digest mismatch fails closed;
- CandidateSet session mismatch fails closed;
- duplicate candidate ids fail closed;
- unsupported CandidateSet contract version fails closed;
- invalid enum/digest values fail before transcript rendering;
- response size limits fail closed;
- `product_context_required` remains typed;
- untrusted limitation prose does not enter command output;
- errors never render as aligned/safe/clear.

## Stop line

After this remediation slice is green, pause again for adversarial review.

Do not yet implement:

- MCP #871 consumption;
- candidate selection/prepare/commit;
- raw review panes;
- installer migration;
- automatic promotion/rejection;
- semantic provider work inside Integrations.

The next tranche begins only if the next adversarial review confirms the main-thread/session-routing model, response envelope, response-binding model, and host-context security posture remain correct.