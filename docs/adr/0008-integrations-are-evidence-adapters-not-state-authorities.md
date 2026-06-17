# ADR-0008: Bicameral Integrations Are Evidence Adapters, Not State Authorities

Status: Proposed
Date: 2026-06-04
Owner: BicameralAI

## Context

Bicameral MCP needs integrations with external systems such as source control tools, project management platforms, documentation systems, communication platforms, security scanners, observability tools, CRM systems, and MCP servers.

These systems contain useful evidence, but they should not become authoritative decision systems inside Bicameral.

Without a clear boundary, connectors can accidentally become state owners, policy bypasses, or unreviewed automation surfaces.

## Decision

Bicameral integrations will normalize external signals into Bicameral-compatible evidence, candidates, events, notifications, and proposed actions.

Integrations will not:

- Own canonical Bicameral state
- Silently approve decisions
- Treat external source claims as accepted truth
- Bypass Bicameral governance
- Execute high-risk external mutations without policy

External tools remain sources, not authorities.

## Consequences

### Positive

- Bicameral keeps a clear governance boundary.
- Connectors remain replaceable and testable.
- External systems can be integrated without becoming decision authorities.
- Evidence provenance is preserved.
- Candidate decisions can be reviewed before acceptance.

### Negative

- Some workflows require an extra review step.
- Connector implementation must include normalization and classification logic.
- External write actions require more design work.

### Neutral

- Integrations may still support proposed writes or governed writes, but only through explicit trust tiers and review policies.

## Implementation Requirements

Each adapter must emit records conforming to the governed adapter contract.

Minimum supported record types:

- Evidence record
- Candidate record
- Audit record

Optional record types:

- Notification record
- Proposed action record

Each adapter must declare:

- Adapter version
- Mapping version
- Provider API version where applicable
- Supported event types
- Unsupported event types
- Trust tier
- Data classification assumptions

## Acceptance Criteria

This ADR is implemented when:

- `GOVERNED_ADAPTER_CONTRACT.md` exists
- `TRUST_TIER_MODEL.md` exists
- At least one adapter emits normalized evidence records
- Unknown payloads are quarantined
- External state mutation is impossible without explicit proposed-action or governed-write policy

## Amendment (ADR-0017, 2026-06-16)

ADR-0017 (Provider Acquisition Contract) introduces a provider **discovery** edge. Its one write
operation, `create_provider_resource` (e.g. a provider-safe Drive folder), is **not** a carve-out from
this ADR: it is modeled as a `ProposedAction` (ADR-0011) — integrations proposes, the bot governs and
executes it as `Egress`. Integrations holds no approval/execution/retry state for it. The read-only
authority invariant therefore holds unchanged: the discovery edge adds **no** new write authority.
