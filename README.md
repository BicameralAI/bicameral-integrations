# Bicameral Integrations

**Bicameral Integrations** contains open-source source adapters and EM-safe mods for Bicameral.

Integrations are the expressive edge of the system. They understand Jira, Linear, Slack, Notion, GitHub, support email, meetings, and customer-specific workflows. They do not own canonical state.

## Key Features

- **Source adapters** – transform external tool payloads into typed Bicameral objects.
- **EM-safe mods** – lightweight YAML/prompt/fixture packages for dependency risk, security mentions, routing hints, and review suggestions.
- **Gateway compatibility** – every adapter targets `bicameral-bot/protocol/` contracts.
- **Source evidence preservation** – adapters preserve excerpts, refs, source type, timestamps, and prompt/manifest versions where relevant.
- **Trust-tier configuration** – high-signal sources can auto-create candidates; noisy sources can require manual gating.

## High-level Architecture

```text
External source
Jira / Linear / Slack / Notion / GitHub / email / meetings
        │
        ▼
bicameral-integrations adapter or mod
        │ emits typed protocol objects
        ▼
bicameral-bot gateway
        │
        ▼
local daemon governance + review + storage adapter
```

## Repository Layout

```text
├── adapters/                # Source adapters, added as implementation lands
├── mods/                    # EM-safe mod examples and fixtures
├── docs/adr/                # Integration-specific architecture decisions
├── CONTEXT.md               # Project glossary and resolved terms
└── README.md                # You are here
```

## Related Repositories

- [`bicameral-bot`](https://github.com/BicameralAI/bicameral-bot) – local daemon/gateway and embedded protocol contracts.
- [`bicameral-mcp`](https://github.com/BicameralAI/bicameral-mcp) – agent-facing tool surface; not a source-adapter repo.
- [`bicameral-cloud`](https://github.com/BicameralAI/bicameral-cloud) – hosted code graph/oracle; not the adapter host by default.

## Mod Safety Contract

Mods may emit candidates, evidence, hints, dependency signals, advisories, and suggested review commands. Mods may not write `.bicameral/decisions/*.yaml`, approve signoff, mark compliance resolved, create blocking CI results directly, collapse confidence surfaces, or bypass governance policy.

## Testing

```bash
pytest -v tests/
```
