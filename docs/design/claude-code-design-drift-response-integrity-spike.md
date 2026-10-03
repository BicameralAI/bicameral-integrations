# Claude Code Design Drift: Product Routing and Response Integrity Spike

Status: implementation spike for #319  
Program: #311  
Client workstream: #313  
Upstream routing seam: BicameralAI/bicameral-mcp#871  
Live semantic provider dependency: BicameralAI/bicameral-bot#958 / #1066

## Purpose

This note freezes the architectural frame for the next bounded Design Drift implementation slice before broader Claude UX, installer composition, or candidate action flows proceed.

The spike addresses two separate questions:

1. How does a Claude-hosted client establish the correct Bicameral Product without turning a filesystem path into Product identity?
2. How does the plugin know that a Managed MCP result and CandidateSet actually belong to the exact Plan it asked Bicameral to analyze?

The answer to both is to reuse Bicameral authority rather than reconstructing it inside the plugin.

## Decision summary

### Product routing

Claude Code may provide a host workspace path. That path is a routing hint only.

The intended host-neutral flow is:

```text
Claude host lifecycle event
  provider-authored cwd/workspace hint
        |
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

The plugin must never infer Product identity from:

- cwd by itself;
- folder names;
- git remotes;
- CLAUDE.md or transcript content;
- model reasoning;
- environment guesses;
- first/nearest workspace binding;
- prior Product state from another process.

This preserves the architecture already used by the managed SessionStart hook: host path is a candidate routing path, while the daemon owns resolution.

### Response integrity

A successful MCP call is not sufficient evidence that the returned result belongs to the current Plan.

The client therefore binds every rendered result to the exact request identity:

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
client validation
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

Any mismatch is an integrity failure, not a drift result.

## Provider facts

Anthropic's current Hooks reference documents `cwd` as a common hook input field and states that it follows Claude after worktree/directory changes. This makes it useful as a current host routing hint but unsuitable as a stable identity.

Canonical provider source:

- https://code.claude.com/docs/en/hooks

The Claude Mod uses `classic.PostToolUse`; Anthropic defines `classic.<Event>` as the settings-hook-compatible event bridge, so its payload follows the corresponding hook event schema.

Canonical Mod sources remain cataloged in:

- `plugins/claude-code/README.md`
- `plugins/claude-code/design-drift/references.md`

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

A client that parses only the first JSON text block is incomplete and can silently discard the review object.

## Implemented spike behavior

`plugins/claude-code/design-drift/hooks/drift.js` now:

- parses `structuredContent` plus every JSON text result block;
- preserves typed MCP errors before attempting semantic interpretation;
- requires the daemon-returned Managed Planning boundary;
- compares host kind, host session, host turn, and exact Plan digest against the request;
- requires a daemon-returned Product id and checks an explicitly requested Product when present;
- finds the additive CandidateSet surface when present;
- requires CandidateSet contract version 1;
- validates CandidateSet id, generation, digest, and lease identity;
- checks CandidateSet Product, host session, Plan digest, and spec-binding digest;
- rejects duplicate candidate ids;
- retains only bounded CandidateSet metadata/counts in the plugin presentation model;
- maps `product_context_required`, protocol mismatch, unavailable capability, and unavailable MCP to distinct states;
- does not put raw candidate/spec/limitation prose into `/bicameral-drift` command output.

## Security rationale

### Do not launder transport success into semantic success

A returned JSON object can still be stale, crossed, malformed, or bound to another Product/session/Plan.

Identity validation occurs before semantic state mapping.

### Do not turn command output into a prompt-injection bridge

Claude command return text becomes conversational context. Candidate text, governing-spec prose, provider limitation detail, and source excerpts are therefore treated as untrusted content.

During this spike, `/bicameral-drift` may show only bounded typed facts such as:

- result state;
- outcome/status classes;
- spec-binding digest;
- CandidateSet id/generation/count;
- limitation codes.

Human-readable candidate/spec prose requires a separately reviewed human-only pane or another governed context-injection design.

### Do not create Product authority in the host

Workspace resolution is routing, not identity creation. CandidateSet state is transient working state, not canonical Product state. The plugin cannot promote, approve, or confirm anything in this slice.

## Known blockers and intentional non-solutions

### MCP Product-routing seam

Until MCP #871 exists, a fresh Claude plugin session may still receive `product_context_required`.

The plugin reports that state honestly. It does not infer or auto-invent Product context.

### Live ClaimTrace producer

Current Bot Managed Preflight treats absent `claim_trace` as provider unavailable. MCP does not produce a live trace itself.

Therefore normal semantic Design Drift remains activation-blocked on Bot #958 / #1066 or an accepted successor.

Integrations must not duplicate the semantic provider merely to make the UI look alive.

## Tests required for this spike

Host-neutral Node-backed fixtures must prove:

- exact Plan hashing and tool-use fallback;
- no transcript recovery when exact Plan bytes are missing;
- contradiction / timeout / unclassified states remain distinct;
- multi-content response preserves CandidateSet metadata;
- returned Plan digest mismatch fails closed;
- CandidateSet session mismatch fails closed;
- duplicate candidate ids fail closed;
- unsupported CandidateSet contract version fails closed;
- `product_context_required` remains typed;
- untrusted limitation prose does not enter command output;
- errors never render as aligned/safe/clear.

## Stop line

After this spike is green, do not immediately implement:

- MCP #871 consumption;
- candidate selection/prepare/commit;
- raw review panes;
- installer migration;
- automatic promotion/rejection;
- semantic provider work inside Integrations.

Perform an adversarial review first.

The next tranche should begin only after that review confirms the Product-routing seam, response-binding model, and host-context security posture are still correct.