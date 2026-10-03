# Claude Code Host Plugin Family

This directory contains Bicameral integrations packaged for the **Claude Code plugin runtime**. A Claude Code plugin may contain an Anthropic **Mod**, which is JavaScript/TypeScript code executed inside Claude Code's process.

This provider family follows the same documentation discipline used by Bicameral connectors: official provider documentation is cataloged next to the integration, linked from the package README, and refreshed on a defined cadence. Provider behavior must not be reconstructed from memory, examples, or third-party tutorials when an official source exists.

## Documentation layout

```text
plugins/
  README.md                         # host-plugin category contract
  claude-code/
    README.md                       # this provider-family contract
    design-drift/
      README.md                     # product/integration behavior
      references.md                 # canonical provider + Bicameral references
      compatibility.json            # machine-readable tested/required surface
      .claude-plugin/plugin.json    # provider-native manifest
      hooks/
        hooks.json
        register.js
        drift.js
```

Every Claude Code plugin under this directory MUST provide a `references.md` that records:

- official Claude Code plugin and Mod documentation used by the implementation;
- the Mods API and event/reference pages used by code;
- plugin manifest, installation, security/trust, and organization-management documentation where relevant;
- the provider-maintained type declaration source;
- exact provider version floor and tested versions;
- verification date and documentation refresh cadence;
- the exact Claude events and Mods API methods consumed;
- provider behaviors that are security- or authority-relevant;
- Bicameral contracts/ADRs/issues that govern the integration;
- known provider/documentation uncertainties or version-sensitive assumptions.

The package README must link its `references.md`. `compatibility.json` must identify the local reference file and provider documentation verification date so the documentation relationship is machine-auditable.

## Source precedence

Use this precedence when provider sources disagree:

1. **Generated types for the exact Claude Code build under test** (`.claude-plugin/types/`).
2. Official Claude Code Mods/type declarations maintained by Anthropic.
3. Official Claude Code Mods API and Mods reference documentation.
4. Official Claude Code plugin manifest/install/security documentation.
5. Official provider-maintained examples/repositories.
6. Third-party material only as non-authoritative research input.

Anthropic's Mod authoring documentation states that Claude Code writes version-specific TypeScript declarations into `.claude-plugin/types/` and that those declarations describe the exact events and Mods API methods available in the running build. When those generated types disagree with prose documentation, **the generated types for the tested build win**.

## API / SDK terminology

For Claude Code Mods, the runtime programming surface used by Bicameral is the **Mods API** exposed to hook handlers as `$`, together with the generated TypeScript declarations for that Claude Code build.

The **Claude Agent SDK is a separate product/runtime surface**. Do not treat Agent SDK documentation as the implementation contract for a Claude Code Mod unless a future integration explicitly uses the Agent SDK.

For Design Drift v0.1, the declared Mods API surface is intentionally narrow:

- `$.command.register`
- `$.clock.after`
- `$.mcp.call`
- `$.ui.status`
- `$.ui.toast`

Any expansion of that surface requires an update to the package `references.md`, `compatibility.json`, security review, and tests.

## Provider event doctrine

Claude Code settings-hook events are exposed to Mods as `classic.<Event>` events. Provider event shape is version-sensitive. A package may rely on a provider event only when:

1. the event is documented by Anthropic;
2. the exact fields consumed are present in the generated types or real-host evidence for a supported build; and
3. the package's compatibility contract records the mapping.

Do not recover missing provider fields by scraping transcripts, prompts, or unrelated session state unless a separate architecture decision explicitly approves that behavior.

## Security doctrine

Claude Code Mods run with the user's permissions and are not a Bicameral security boundary. Anthropic documents that Mods may access files, processes, network, secrets, session data, model usage, prompts, and tool approvals when they invoke the corresponding APIs.

Therefore each Bicameral Claude Code plugin MUST:

- declare every Mods API namespace/method it uses;
- fail review if undeclared privileged calls appear;
- avoid broader privileges when a narrower connected MCP/API boundary works;
- document Mod-chain interception/rewrite risk for calls made through the Mods API;
- keep canonical Bicameral authority outside Claude Code;
- validate provider/runtime compatibility before claiming support.

## Validation requirements

Before a Claude Code plugin is marked supported for a provider version, retain evidence for:

1. `claude plugin validate <plugin-dir>` on the exact candidate package;
2. generated `.claude-plugin/types/` for the tested Claude Code build, or an equivalent retained type-surface digest/version witness;
3. successful load using the real Claude Code runtime;
4. exact event delivery used by the integration;
5. every Mods API method used by the integration;
6. degraded/version-skew behavior;
7. install/update/repair/uninstall behavior;
8. security review against the declared capability surface.

Provider minimum version is not proof of support. `tested_versions` remains empty until real-host evidence exists.

## Documentation freshness

Claude Code Mods are a **high-risk, fast-moving host integration surface**. Provider documentation must be reviewed at least monthly while the integration is active, and immediately when:

- Claude Code changes the Mod API or event model;
- generated types change for an API/event we consume;
- plugin manifest/install behavior changes;
- security/trust behavior changes;
- organization-managed Mod controls change;
- a supported Claude Code version is added or removed.

Each child integration records its own last-verified date and findings in `references.md`.