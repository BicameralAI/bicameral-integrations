# ADR-0010: Product-Agnostic Candidate Harvesting

Status: Proposed
Date: 2026-06-04
Owner: BicameralAI

## Context

Bicameral may identify integration candidates from many sources, including customer workflows, adjacent tools, open-source projects, MCP ecosystem activity, prior implementation work, and internal prototypes.

This is useful for discovery, but candidate discovery must not create architectural dependency or product coupling.

## Decision

Bicameral may harvest integration candidates from external or adjacent tooling, but each candidate must be independently evaluated against Bicameral's own criteria.

Candidate harvesting does not imply:

- Runtime dependency
- Shared authority
- Shared governance
- Shared state
- Shared roadmap ownership
- Product coupling

Bicameral's integration roadmap remains Bicameral-owned.

## Consequences

### Positive

- Bicameral can benefit from prior research and ecosystem awareness.
- Documentation avoids implying dependency on adjacent tools.
- Connector priorities remain grounded in Bicameral-native value.
- Integration design remains portable and product-independent.

### Negative

- Some candidate lists may need deduplication and independent validation.
- Prior implementation details cannot be copied uncritically.
- Candidates with weak official documentation may be deferred even if they were useful elsewhere.

## Implementation Requirements

Each candidate harvested from adjacent tooling must include:

- Source of candidate
- Official docs link
- Bicameral-native value statement
- Recommended trust tier
- Data risk
- Maintenance risk
- Initial adapter mode

The integration catalog must avoid language implying that Bicameral is downstream of or governed by any adjacent product.

## Acceptance Criteria

This ADR is implemented when:

- `INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md` exists
- Catalog entries are justified by Bicameral value, not external product alignment
- Candidate harvesting is explicitly separated from runtime dependency
- Adjacent products are not included as governance authorities unless explicitly designed and approved
