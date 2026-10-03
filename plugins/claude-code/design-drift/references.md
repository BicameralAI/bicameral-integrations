# Claude Code Design Drift — Canonical References

Single place tracking the canonical provider and Bicameral documentation used by the `plugins/claude-code/design-drift` integration.

See also:

- [`plugins/README.md`](../../README.md) for the host-plugin category contract.
- [`plugins/claude-code/README.md`](../README.md) for the Claude Code provider-family documentation and validation rules.
- [`docs/INTEGRATION_DOCS_INDEX.md`](../../../docs/INTEGRATION_DOCS_INDEX.md) for the repository-wide provider-documentation maintenance policy.

## This integration

| Field | Value |
|---|---|
| Provider | Anthropic Claude Code |
| Provider surface | Claude Code plugin containing an Anthropic Mod |
| Integration role | Host-native advisory presentation / lifecycle adapter |
| Bicameral capability | Managed MCP post-Planning design-plan analysis |
| Package path | `plugins/claude-code/design-drift/` |
| Program | `#311` |
| Implementation | `#312`, `#313`, `#314` |
| Managed install | `#315` |
| Terminal/security acceptance | `#316` |
| Provider minimum | Claude Code `2.1.287` |
| Bicameral tested versions | None yet; `compatibility.json:test_versions` remains empty until real-host evidence exists |
| Documentation risk | High / fast-moving host runtime |
| Refresh cadence | Monthly, plus event-driven review on provider/runtime changes |
| Last provider-doc verification | 2026-10-03 |

## Official provider documentation

These are the canonical external references for this integration. Prefer these over blog posts, examples, screenshots, recollection, or third-party tutorials.

| Kind | Canonical link | Why this integration uses it |
|---|---|---|
| Mods overview | https://code.claude.com/docs/en/plugins/mods/overview | Defines what a Mod is, where it runs, trust boundary, minimum version, plugin relationship, and comparison with settings hooks/MCP/skills. |
| Create a Mod | https://code.claude.com/docs/en/plugins/mods/create | Defines provider-native package shape (`.claude-plugin/plugin.json`, `hooks/hooks.json`, hooks module), local loading, `claude plugin validate`, generated types, and authoring workflow. |
| Mods reference | https://code.claude.com/docs/en/plugins/mods/reference | Canonical event catalog, `classic.<Event>` bridge, Mods API method inventory, render sites, limits, and chain/interception behavior. |
| Mods API | https://code.claude.com/docs/en/plugins/mods/api | Defines `$` namespaces and calls including `$.mcp.call`, files/process/network/session access, and the fact that Mods API calls are interceptable events. |
| Hooks reference | https://code.claude.com/docs/en/hooks | Defines settings-hook event payloads used by `classic.PostToolUse`, including `PostToolUse` event semantics and host-provided tool result data. |
| Plugin manifest reference | https://code.claude.com/docs/en/plugins/manifest-reference | Canonical `plugin.json` fields, paths, component declarations, validation behavior, configuration, and standard layout. |
| Install/manage plugins | https://code.claude.com/docs/en/plugins/install | Installation scopes, marketplace/plugin lifecycle, enable/disable/update/uninstall behavior, and local plugin loading. |
| Plugin security/trust | https://code.claude.com/docs/en/plugins/security | Provider security model: plugins/Mods can execute with user privileges, operate outside Claude tool sandboxing, affect context, and change across updates. |
| Manage Mods for organizations | https://code.claude.com/docs/en/plugins/mods/admin | Organization controls, managed Mod ordering/policy, and restrictions relevant to enterprise installation. |
| Provider-maintained Mod types | https://github.com/anthropics/claude-code/blob/main/mods/types/claude-code.d.ts | Online provider-maintained type surface. The exact local generated declarations for the tested Claude Code build have higher precedence. |
| Claude Code changelog | https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md | Release changes and regression/drift review source for supported versions. |

## API / SDK interpretation

The implementation contract for this plugin is **not** the Claude Agent SDK.

For a Claude Code Mod, the relevant SDK-like/runtime surface is:

1. the **Mods API** passed to a hook as `$`;
2. the exact events available to the running Claude Code build; and
3. the **version-specific TypeScript declaration files** Claude Code generates under `.claude-plugin/types/` when it loads a Mod from a plugin directory.

Anthropic's Mod authoring documentation states that those generated declaration files describe the exact events and Mods API methods for the installed build and should be trusted over prose documentation when they disagree.

The Claude Agent SDK may be relevant to another Bicameral integration in the future, but it is not a dependency or authority source for Design Drift v0.1.

## Provider-native files used by this package

| File | Provider contract |
|---|---|
| `.claude-plugin/plugin.json` | Claude Code plugin manifest |
| `hooks/hooks.json` | Declares the Mod hooks module through `modules` |
| `hooks/register.js` | Registers Claude Code events and invokes Mods API methods |
| `.claude-plugin/types/` | Generated by the exact Claude Code build during real-host validation; must not be fabricated or treated as portable across versions |

## Exact provider surface consumed by v0.1

### Events

| Event | Purpose | Provider reference |
|---|---|---|
| `session.start` | Reset bounded in-memory state and register `/bicameral-drift` | Mods reference / generated types |
| `classic.PostToolUse` | Receive the provider's settings-hook-compatible post-tool payload and recognize `ExitPlanMode` | Mods reference + Hooks reference + generated types |
| `command.run` | Handle explicit `/bicameral-drift` review/refresh | Mods reference / generated types |
| `session.end` | Erase ephemeral plugin state | Mods reference / generated types |

### Mods API methods

| Method | Purpose | V0.1 authority posture |
|---|---|---|
| `$.command.register` | Register the local review command | UI convenience only |
| `$.clock.after` | Run advisory analysis without blocking the lifecycle event | No Product authority |
| `$.mcp.call` | Call an already-connected `bicameral` MCP server | Transport only; MCP/daemon remain authoritative |
| `$.ui.status` | Show bounded status | Presentation only |
| `$.ui.toast` | Surface contradiction attention signal | Presentation only |

No other Mods API method is approved for v0.1 without updating `compatibility.json`, this file, security review, and tests.

## Explicitly prohibited / unused provider capabilities in v0.1

Although the provider supports them, this integration does not currently use:

- `$.fs` file read/write/list/stat;
- `$.process` run/spawn;
- `$.http` direct network access;
- `$.env` environment access;
- `$.settings` settings inspection;
- `$.session.messages` transcript access;
- `$.model` model calls;
- `$.prompt` submit/read/rewrite paths;
- `$.tool.register` or `$.tool.call`;
- Mod-driven tool approval;
- direct settings mutation;
- arbitrary process execution;
- arbitrary network destinations.

This exclusion list is part of the security contract, not merely an implementation accident.

## Version-sensitive assumptions that require retained evidence

Do not mark this plugin supported solely because the provider docs contain these features. The exact candidate Claude Code build must prove them.

1. `classic.PostToolUse` is available to the Mod.
2. Its event object exposes the exact fields we consume for the planning boundary.
3. `ExitPlanMode` returns exact Plan bytes in the expected `tool_response.plan` field.
4. `turn_id` and/or `tool_use_id` are available with the semantics expected by Bicameral.
5. `crypto.subtle` and `TextEncoder` are available for exact Plan hashing.
6. `$.mcp.call` can reach the already-connected `bicameral` server and preserves the expected MCP response form.
7. `$.clock.after` permits the non-blocking background call pattern used by the Mod.
8. `$.ui.status`, `$.ui.toast`, and command output behave on every surface we claim to support.
9. Mod-chain ordering/interception behavior does not silently strengthen the Mod into a trusted evidence channel.

## Security-relevant provider facts

Provider documentation currently establishes the following constraints that directly affect Bicameral design:

- Mods execute inside Claude Code with the user's permissions and are not sandboxed by Claude's tool sandbox.
- A Mod can access powerful file/process/network/session/model/tool-approval capabilities when it calls the corresponding Mods API.
- Mods API calls are themselves events and an earlier Mod in the chain can observe, rewrite, refuse, or replace a later Mod's calls.
- Plugin updates can change executable package contents, so install/update provenance matters.
- Provider-drawn UI availability differs by Claude surface even when hooks still execute.

For those reasons, the Design Drift Mod is a **host advisory view**, not canonical governance evidence or a security boundary.

## Bicameral source-of-truth references

| Concern | Canonical Bicameral source |
|---|---|
| Host-plugin category boundary | `plugins/README.md` |
| Claude provider-family documentation contract | `plugins/claude-code/README.md` |
| Integration architecture | `docs/adr/0021-claude-code-plugin-design-drift-boundary.md` |
| Product requirements | `docs/prd/claude-code-design-drift-plugin.md` |
| Implementation sequencing | `docs/design/claude-code-design-drift-implementation-plan.md` |
| Package/runtime declaration | `plugins/claude-code/design-drift/compatibility.json` |
| Package behavior | `plugins/claude-code/design-drift/README.md` |
| Managed MCP wire contract | `BicameralAI/bicameral-mcp` current `bicameral.preflight` schema/renderer |
| Semantic analysis authority | `BicameralAI/bicameral-bot` current Managed Preflight / SMR contracts |
| Live ClaimTrace provider dependency | `BicameralAI/bicameral-bot#958` / `#1066` |
| Program | `BicameralAI/bicameral-integrations#311` |
| Package/client/UX slices | `#312`, `#313`, `#314` |
| Managed install migration | `#315` |
| Real-host/security acceptance | `#316` |

## Adversarial-review findings that affect documentation and compatibility

The 2026-10-03 adversarial review of PR #318 identified several facts that must remain visible in this reference record:

1. Current Bot semantic analysis returns `provider_unavailable` when no live ClaimTrace is supplied. Design Drift activation therefore depends on the live ClaimTrace producer rather than recreating extraction in Integrations.
2. MCP Product selection is process-local; a daemon-side workspace resolution does not automatically establish the MCP server's selected Product.
3. MCP may return ordinary preflight content plus an additive CandidateSet review surface. A host adapter must not assume the first JSON text block is the whole semantic result.
4. Returned Managed Preflight and CandidateSet identities must be validated against the requested Product/session/turn/Plan digest/generation before presentation.
5. Because Mods API calls may be intercepted by earlier Mods, Claude-local presentation is not independently trusted evidence unless a stronger daemon-authenticated binding is introduced.
6. Raw provider/spec/candidate prose should not be injected into Claude's transcript merely for presentation convenience; human-only UI is preferred for untrusted text.

## Refresh checklist

At every monthly or event-driven refresh:

- [ ] Verify every official URL above still resolves to the intended provider page.
- [ ] Review Claude Code changelog since the previous verification.
- [ ] Compare the exact generated Mod types for supported/tested versions with the events/API calls listed here.
- [ ] Re-run `claude plugin validate` and record the discovered hooks/calls.
- [ ] Confirm minimum provider version and tested versions.
- [ ] Check Mod API additions/removals/behavior changes.
- [ ] Check event payload changes for `classic.PostToolUse` / `ExitPlanMode`.
- [ ] Check plugin install/update/uninstall behavior changes.
- [ ] Check security/trust and organization-management changes.
- [ ] Reconcile any changed behavior into `compatibility.json`, tests, ADR/PRD, and implementation before support claims continue.

## Verification record

### 2026-10-03

Verified against current official Anthropic documentation before and during initial implementation/adversarial review.

Confirmed from provider docs:

- Mods are Claude Code plugins implemented as JavaScript/TypeScript event handlers.
- Mods require Claude Code 2.1.287 or later.
- `classic.<Event>` exposes settings-hook events to Mods.
- `$.mcp.call` calls a tool on a connected MCP server.
- generated `.claude-plugin/types/` are version-specific and outrank prose docs when inconsistent.
- `claude plugin validate` statically reports Mod events and API calls.
- Mods run with user permissions and Mods API calls can be intercepted by earlier Mods.

Real Claude Code terminal validation is still pending under #316; this verification is documentation/contract evidence, not terminal acceptance.