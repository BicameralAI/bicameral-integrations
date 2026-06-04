# Notion Connector

Provider-facing Notion adapter. **Status: Candidate** (catalog docs, priority P0, default trust tier T1/T3).

This folder is scaffolded per the Bicameral integration lifecycle; the parse
surface (`connector.py`) is not yet implemented. It is a Phase-1 foundation
candidate from the [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Intended role

evidence + event — emits provider-neutral `adapter.core` Observations to `pipeline.normalize()`; no canonical-state writes (evidence adapter, not state authority — ADR-0008).

## References

- Canonical doc links: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)

## Connectors

- [Connectors](../README.md)
- [Adapter Core](../../adapter/core/README.md)
