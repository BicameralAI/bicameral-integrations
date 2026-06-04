# Security Mentions Mod

The Security Mentions mod is an advisory manifest for auth, token, secret, PII, webhook verification, and transport-exposure signals.

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
| `id` | `security-mentions` |
| `version` | `0.1.0` |
| `name` | `Security Mentions` |
| Source | [`manifest.yaml`](manifest.yaml) |

## Allowed Outputs

- `advisory_governance_result`
- `routing_hint`
- `source_evidence_annotation`

## Forbidden Actions

- `write_canonical_decision`
- `approve_signoff`
- `resolve_compliance`
- `create_blocking_ci_result`

## Contributor Expectations

The mod may surface security-relevant evidence and recommend routing. It must not treat a mention as proof of vulnerability, approve remediation, resolve compliance, or create blocking CI results directly.

When adding behavior, include fixtures for positive and negative examples and update the parent [mods README](../README.md).

## Related Documentation

- [EM-Safe Mods](../README.md)
- [Repository README](../../README.md)
- [Adapter Core Sensitive Evidence Screen](../../adapter/core/README.md#sensitive-evidence-screen)
- [ADR-0007 EM-Safe Mod Boundary](../../docs/adr/0007-em-safe-mod-boundary.md)
