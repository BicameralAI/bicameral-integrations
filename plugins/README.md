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

## Documentation contract

Host plugins follow the same provider-documentation discipline as connectors.

Every provider family under `plugins/` MUST document where its official platform/API/SDK/runtime documentation lives, how source precedence works, and how often that documentation is re-verified. Every concrete plugin integration MUST then carry a local `references.md` that binds the implementation to the exact provider documentation and Bicameral contracts it consumes.

Expected structure:

```text
plugins/
  README.md                         # category contract
  <provider>/
    README.md                       # provider-family docs/API/SDK rules
    <integration>/
      README.md                     # integration behavior
      references.md                 # canonical provider + Bicameral references
      compatibility.json            # machine-readable runtime/authority declaration
```

The repository-wide documentation source precedence and maintenance policy live in [`docs/INTEGRATION_DOCS_INDEX.md`](../docs/INTEGRATION_DOCS_INDEX.md). Provider-local reference records should mirror that policy and add host-runtime details that the generic integration index cannot express cleanly.

A provider-family README should identify, where applicable:

- official platform/plugin documentation;
- event/lifecycle reference;
- API/runtime SDK documentation;
- generated or published type/schema references;
- manifest/package specification;
- installation/update/uninstall documentation;
- authentication/permission/security model;
- organization/enterprise controls;
- changelog/release notes;
- provider-maintained reference implementation/examples.

A concrete plugin `references.md` must additionally record:

- exact provider events and APIs consumed;
- version floor and tested versions;
- source precedence when provider docs/types disagree;
- documentation verification date and refresh cadence;
- security/authority-relevant provider facts;
- known version-sensitive assumptions;
- corresponding Bicameral ADR/PRD/contracts/issues;
- validation evidence required before support is claimed.

`compatibility.json` must point to the local reference record and include the provider-doc verification date so this relationship can be checked mechanically.

## Package expectations

Each plugin integration should provide:

- provider-native package/manifest files;
- a Bicameral integration descriptor;
- a provider-family documentation record;
- a package-local `references.md` cataloging canonical provider/API/SDK/runtime documentation;
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

Provider-family docs: `plugins/claude-code/README.md`  
Canonical provider references: `plugins/claude-code/design-drift/references.md`  
Program: #311  
ADR: `docs/adr/0021-claude-code-plugin-design-drift-boundary.md`  
PRD: `docs/prd/claude-code-design-drift-plugin.md`  
Implementation plan: `docs/design/claude-code-design-drift-implementation-plan.md`

## Maturity

Creating a directory under `plugins/` does not make a plugin supported or release-ready.

A plugin becomes supported only after its provider documentation, compatibility, security, install, and real-host acceptance evidence is complete and the relevant Bicameral release explicitly includes it.