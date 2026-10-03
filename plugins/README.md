# Host Plugins

`plugins/` contains installable packages that run inside third-party developer/runtime hosts and expose Bicameral capabilities in the host's native experience.

This is a **packaging and host-integration category**, not a Bicameral state-authority category.

## Why this category exists

The repository already has two established integration families:

```text
connectors/   external systems -> Bicameral evidence
mods/         Bicameral evidence -> EM-safe advisory enrichment
```

A host plugin is different:

```text
plugins/      Bicameral capability <-> third-party host experience
```

Host plugins may react to host lifecycle events, render host-native UI, or expose host-native commands, but they must consume Bicameral capability through accepted contracts. They do not gain canonical authority because they run closer to the user.

## Naming note

Anthropic calls executable Claude Code plugin handlers **Mods**. Bicameral already uses `mods/` for its own EM-safe advisory processors. These concepts are intentionally kept separate.

- `mods/` = Bicameral advisory processor family.
- `plugins/claude-code/...` = installable Claude plugin, which may contain an Anthropic Mod.

Do not move Anthropic Mod packages into `mods/` merely because the provider uses the same noun.

## Authority rules

A host plugin MAY:

- translate host lifecycle events into accepted Bicameral requests;
- call an approved Bicameral MCP/API capability;
- render exact Bicameral results in host-native UI;
- expose host-native commands;
- retain bounded ephemeral presentation state;
- provide provider-specific compatibility and installation metadata.

A host plugin MUST NOT, unless a separate accepted architecture decision explicitly grants it:

- define Product truth;
- create a parallel canonical store;
- reinterpret missing/unknown evidence as success;
- manufacture Product identity or authority from host state;
- bypass Bicameral policy/approval/confirmation;
- treat host permission as Bicameral action authority;
- silently broaden the host's permission model;
- become required for core Bicameral correctness.

## Package expectations

Each plugin integration should provide:

- provider-native package/manifest files;
- a Bicameral integration descriptor;
- provider/minimum/tested version declarations;
- Bicameral protocol/capability requirements;
- declared host events/API calls;
- network/process/filesystem capability declarations;
- explicit canonical-state authority declaration;
- package validation/tests;
- install/update/repair/uninstall expectations;
- security review proportionate to the host privileges available;
- real-host terminal evidence before claiming production readiness.

## Initial plugin

`claude-code/design-drift/` is the first host plugin family. It exposes the existing Managed MCP design-plan drift capability inside Claude Code.

Program: #311  
ADR: `docs/adr/0021-claude-code-plugin-design-drift-boundary.md`  
PRD: `docs/prd/claude-code-design-drift-plugin.md`  
Implementation plan: `docs/design/claude-code-design-drift-implementation-plan.md`

## Maturity

Creating a directory under `plugins/` does not make a plugin supported or release-ready.

A plugin becomes supported only after its own compatibility, security, install, and real-host acceptance evidence is complete and the relevant Bicameral release explicitly includes it.