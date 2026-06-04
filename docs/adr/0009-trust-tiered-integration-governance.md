# ADR-0009: Trust-Tiered Integration Governance

Status: Proposed
Date: 2026-06-04
Owner: BicameralAI

## Context

Bicameral integrations vary widely in risk.

A SARIF file import does not carry the same risk as a connector that can post to GitHub, read customer emails, access production data, or control an MCP server with filesystem and shell tools.

A single generic integration permission model would either be too permissive or so restrictive that it becomes useless, which is software governance's favorite way to ruin lunch.

## Decision

Bicameral will classify integrations and connector operations using a trust tier model:

- T0: Static import
- T1: Authenticated read
- T2: Event ingest and notification
- T3: Proposed write
- T4: Governed write
- T5: Restricted or prohibited

The highest applicable tier governs the operation.

Data sensitivity and action sensitivity are evaluated separately and may raise review requirements.

## Consequences

### Positive

- Read-only connectors can ship safely earlier.
- Write-capable connectors require explicit policy.
- High-risk integrations are clearly separated.
- MCP and agentic tool surfaces can be handled without pretending they are ordinary APIs.

### Negative

- More metadata must be maintained per connector.
- Some connectors may need multiple trust tiers by capability.
- Review routing becomes part of connector design.

## Implementation Requirements

Each integration catalog entry must include:

- Default trust tier
- Maximum allowed action without review
- Data classification
- PII classification
- Write risk
- Maintenance risk

Each adapter must enforce:

- Scope boundaries
- Redaction requirements
- Audit logging
- Quarantine for unknown events
- Human review for proposed writes
- Policy reference for governed writes

## Acceptance Criteria

This ADR is implemented when:

- `TRUST_TIER_MODEL.md` exists
- Each candidate in the catalog has an assigned default trust tier
- Adapter fixtures include at least one blocked or quarantined event
- Write-capable operations require proposed-action records or governed-write policies
