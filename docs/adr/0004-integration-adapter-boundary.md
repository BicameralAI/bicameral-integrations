# ADR-0004: Integration Adapter Boundary

**Date:** 2026-06-02  
**Status:** proposed  
**Level:** L1

## Problem

`bicameral-mcp` currently contains source-specific integration behavior next to
MCP transport, ingest gates, durable ledger writes, governance policy, and
operator CLI code. Moving integrations into this repository without a boundary
would copy core authority into the edge layer.

## Decision

`bicameral-integrations` owns source-specific connector logic, the universal
adapter contract, and mod logic.
`bicameral-mcp` remains the authority for MCP transport, ingest gates, durable
ledger writes, governance policy, signoff, and compliance state.

The repository surface is split into:

- **Connectors**: provider-facing code that knows external APIs, auth flows,
  pagination, webhooks, provider ids, and retries.
- **Universal adapter**: Bicameral-facing normalization pipeline that converts
  connector observations into neutral emissions with preserved evidence.
- **Mods**: advisory post-processors that annotate emissions and suggest review
  routing without authority.

## Consequences

The integration layer can evolve independently while preserving Bicameral's
authority boundary. Source-specific connector code can be open, swappable, and
fixture tested without being allowed to write canonical decisions or resolve
compliance. Each provider gets a connector; the adapter remains one shared
contract and pipeline.

Extraction from `bicameral-mcp` should proceed component by component. Read-only
connector parsers and observation builders move first; webhook connector
handlers move only after the handler interface and security tests are stable.

## Non-Goals

- This ADR does not move the MCP server into this repository.
- This ADR does not move the durable ledger or governance engine.
- This ADR does not grant connectors, the adapter, or mods canonical write authority.
