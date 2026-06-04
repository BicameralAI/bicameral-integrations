# Jira Connector

Provider-facing Jira Cloud adapter. **Status: Candidate** (catalog
project-management, priority P0, default trust tier T1/T3). A Phase-1 foundation
candidate from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

This folder is scaffolded per the Bicameral integration lifecycle; the parse
surface (`connector.py`) is not yet implemented. When built, it will map a Jira
issue (webhook event or REST `issue` object) to a neutral `Observation` and emit
it to `pipeline.normalize()` — read-only evidence, no canonical-state writes
(ADR-0008).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
