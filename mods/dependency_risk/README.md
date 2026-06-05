# Dependency Risk Mod

Status: Scoped

Advisory mod for surfacing dependency-risk signals from connector and project
evidence — upgrades, pins, SDK drift, and version-compatibility concerns — so a
reviewer can weigh them before a change lands. Advisory only: it annotates and
routes; it never blocks or approves (see the [mod safety contract](../README.md)).

## Scope

- Dependency upgrades and version bumps that change behavior or surface area.
- Unpinned or loosely pinned dependencies in changed manifests.
- SDK / client-library drift against a connector's documented provider contract.
- Version conflicts and incompatibility risk across the dependency tree.

## Outputs

- `source_evidence_annotation`
- `advisory_governance_result`
- `routing_hint`

## References

See [references.md](references.md).
