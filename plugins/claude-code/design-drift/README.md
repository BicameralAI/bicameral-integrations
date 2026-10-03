# Bicameral Design Drift for Claude Code

**Status:** Planned under #311. Implementation has not landed yet.

Bicameral Design Drift is a Claude Code plugin that presents Bicameral's existing Managed MCP design-plan drift analysis inside the active Claude coding session.

> **See when Claude's implementation plan has drifted from the accepted Bicameral design before implementation starts.**

## What this plugin is

A thin Claude-specific adapter and presentation package:

```text
Claude Code
  -> this plugin
  -> existing Bicameral MCP / daemon capability
  -> bicameral-bot Managed MCP drift analysis
```

The plugin should make the result visible and understandable. It does not become the drift engine.

## What owns truth

- `bicameral-bot` owns governing-spec binding, drift/candidate semantics, Product state, promotion/rejection semantics, and canonical receipts.
- `bicameral-mcp` / the accepted daemon API owns the host-neutral capability/transport boundary.
- this plugin owns Claude lifecycle adaptation, UI, commands, compatibility handling, and ephemeral presentation state.
- the human and existing Bicameral daemon authority own consequence-bearing confirmation.

## Planned package shape

```text
.claude-plugin/
  plugin.json
hooks/
  hooks.json
  register.ts
src/
  compatibility.ts
  planning-boundary.ts
  drift-client.ts
  presentation-model.ts
  state.ts
  render.ts
  commands.ts
  diagnostics.ts
fixtures/
tests/
integration.json
package.json
README.md
```

The final shape should follow the current Claude Code plugin/Mod requirements at implementation time.

## Planned user experience

After an authoritative Bicameral planning boundary:

```text
Bicameral · Design Drift: analyzing
```

Then one truthful outcome, for example:

```text
Bicameral · Design Drift: clear in searched scope
Bicameral · Design Drift: 3 proposed · 1 contradiction
Bicameral · Design Drift: incomplete
Bicameral · Design Drift: stale, refresh required
Bicameral · Design Drift: unavailable
```

`/bicameral-drift` provides explicit review/refresh access and is the fallback when automatic trigger or custom drawing cannot be supported safely on the current Claude version/surface.

## Important trigger rule

The plugin must never decide that planning completed by parsing Claude's prose.

Automatic preflight must come from either:

1. an authoritative Bicameral Managed MCP planning-boundary signal, or
2. a documented Claude lifecycle mapping proven against the exact supported Claude version.

Otherwise the plugin falls back to explicit `/bicameral-drift` use.

## V1 security boundary

Claude Mods run with user permissions and are not sandboxed. V1 therefore deliberately does **not** use the full authority available to a Mod.

V1 must not:

- approve Claude tool calls;
- rewrite prompts;
- rewrite tool arguments;
- execute arbitrary processes/shell commands;
- enumerate unrelated secrets/environment state;
- call prompt-controlled arbitrary network destinations;
- directly mutate Bicameral Product/Decision state;
- autonomously confirm promotion/rejection/approval;
- convert unavailable/unknown state into a clean result.

The plugin is a visibility/convenience surface, not a security boundary.

## Surface support

Initial required full UX: Claude Code interactive terminal.

Current Anthropic documentation indicates that Mod hooks can run in more places than custom Mod drawing appears. Therefore every claimed surface must be qualified independently, and non-drawing surfaces require a textual/command fallback.

## Provider requirements

Current official documentation, verified 2026-10-03, states Mods require Claude Code `2.1.287` or later. This is the provider floor, not automatically Bicameral's tested/supported version range.

Official references:

- https://code.claude.com/docs/en/plugins/mods/overview
- https://code.claude.com/docs/en/plugins/mods/reference
- https://code.claude.com/docs/en/plugins/install

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

## Readiness rule

This package is not considered supported when a manifest exists or fixture UI renders. It becomes supported only after #316 retains real Claude Code and real Bicameral end-to-end evidence for the exact candidate revisions.