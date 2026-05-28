# ADR-0001: Open-Core Repository Boundary

Status: accepted

Date: 2026-05-27

## Context

Bicameral is being restructured around an OpenClaw-like local product shape: a public local bot with daemon + gateway boundaries, open-source integrations, shared protocol contracts, and a private hosted optimization layer.

The product must work backwards from cognitive debt. Teams do not merely need documentation. They need decisions, source evidence, code grounding, review state, and governance to remain connected while work is happening.

## Decision

Use the following repository boundary:

- `bicameral-bot` — public local-first app/runtime. Owns daemon, gateway, local review UX, local code grounding, governance policy evaluation, audit trail, and storage-adapter writes.
- `bicameral-mcp` — public agent-facing MCP surface. Owns tools for agents to ingest, preflight, bind, and emit review commands.
- `bicameral-integrations` — public source adapters and EM-safe mods. Owns Jira, Linear, Slack, Notion, GitHub, email, meeting, support, and mod examples.
- `bicameral-protocol` — public shared schemas and conformance tests. Owns typed objects and compatibility rules.
- `bicameral-cloud` — private hosted optimization layer. Owns hosted code graph, cross-branch/cross-repo analysis, conflict oracle, expensive indexing, and accuracy/latency optimization.

## Invariant

The hosted layer produces evidence, suggestions, signals, and advisories. It does not silently create canonical authority.

Canonical promotion remains controlled by governance policy, review commands, and storage adapters.

## Consequences

- The free/public product remains useful and code-grounded locally.
- Paid value concentrates in organization-scale graph intelligence and conflict prevention.
- Integrations and mods can be expressive at the edge while daemon/core remains boring in the middle.
- Repository ownership mirrors product trust boundaries.
