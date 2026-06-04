# Noisy Source Gate Mod

The Noisy Source Gate mod is an advisory manifest for manual-gating high-noise sources such as chat, email, meeting transcripts, and other low-trust inputs unless source trust is explicitly configured higher.

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
| `id` | `noisy-source-gate` |
| `version` | `0.1.0` |
| `name` | `Noisy Source Gate` |
| Source | [`manifest.yaml`](manifest.yaml) |

## Allowed Outputs

- `routing_hint`
- `advisory_governance_result`

## Forbidden Actions

- `write_canonical_decision`
- `approve_signoff`
- `resolve_compliance`
- `create_blocking_ci_result`

## Contributor Expectations

The mod may recommend manual review for noisy source classes. It must not discard evidence silently, mark a finding resolved, or create blocking authority on its own.

When adding behavior, include source-trust fixtures and update the parent [mods README](../README.md).

## Related Documentation

- [EM-Safe Mods](../README.md)
- [Repository README](../../README.md)
- [ADR-0003 Source Trust and Gating](../../docs/adr/0003-source-trust-and-gating.md)
- [ADR-0007 EM-Safe Mod Boundary](../../docs/adr/0007-em-safe-mod-boundary.md)
