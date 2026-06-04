# Dependency Risk Mod

The Dependency Risk mod is an advisory manifest for dependency upgrade, pinning, SDK drift, and compatibility-risk signals.

## Table of Contents

- [Status](#status)
- [Manifest](#manifest)
- [Allowed Outputs](#allowed-outputs)
- [Forbidden Actions](#forbidden-actions)
- [Contributor Expectations](#contributor-expectations)
- [Related Documentation](#related-documentation)

## Status

Implemented:

- Declarative manifest scaffold.
- Explicit advisory outputs.
- Explicit forbidden authority actions.

Deferred:

- Prompt content.
- Fixtures.
- Runtime mod execution.
- Tests.

## Manifest

| Field | Value |
| --- | --- |
| `id` | `dependency-risk` |
| `version` | `0.1.0` |
| `name` | `Dependency Risk` |
| Source | [`manifest.yaml`](manifest.yaml) |

## Allowed Outputs

- `dependency_signal`
- `routing_hint`
- `source_evidence_annotation`

## Forbidden Actions

- `write_canonical_decision`
- `approve_signoff`
- `resolve_compliance`
- `create_blocking_ci_result`

## Contributor Expectations

Any future implementation must keep dependency findings advisory. The mod may identify risk and recommend review routing, but it must not block CI directly, approve changes, or mutate canonical decision state.

When adding behavior, include fixtures that show expected dependency evidence and update the parent [mods README](../README.md).

## Related Documentation

- [EM-Safe Mods](../README.md)
- [Repository README](../../README.md)
- [ADR-0002 EM-Safe Mod Manifest](../../docs/adr/0002-em-safe-mod-manifest.md)
- [ADR-0007 EM-Safe Mod Boundary](../../docs/adr/0007-em-safe-mod-boundary.md)
