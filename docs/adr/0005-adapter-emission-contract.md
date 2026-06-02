# ADR-0005: Adapter Emission Contract

**Date:** 2026-06-02  
**Status:** proposed  
**Level:** L1

## Problem

Existing integrations normalize provider payloads into shapes accepted by
`bicameral-mcp` ingest. That couples provider-specific logic to the current MCP
handler payload format and makes it harder to add conformance tests across
sources.

## Decision

The universal adapter emits a repository-owned neutral contract before any
MCP-specific ingest bridge runs.

The core object model is:

- `SourceRef`: stable source identity and provider reference.
- `SourceEvidence`: excerpt, timestamp, author, URL, and provenance.
- `AdapterEmission`: one reviewable emission produced by the universal adapter.
- `ConfidenceSurface`: named confidence dimensions, never a single opaque score.
- `RoutingHint`: advisory review-routing metadata.
- `AdvisoryResult`: non-authoritative signal for downstream review.

Connectors, the universal adapter, and mods share this object model. They do not
share one runtime interface because they operate at different pipeline stages.

```text
Connector -> UniversalAdapter -> AdapterEmission -> Mod -> Advisory output -> MCP governance
```

## Consequences

Provider-specific code can be tested against stable fixture outputs before it is
bridged into MCP ingest. The contract also gives EM-safe mods a clean input
surface that does not require direct access to raw provider clients or MCP
ledger internals.

## Contract Rules

- Every emission has a stable `source_id`.
- Every emission preserves reviewable evidence.
- Every emission records the adapter or mod version that produced it.
- Confidence is dimensional and explainable.
- Canonical state is not represented as an adapter-owned field.
