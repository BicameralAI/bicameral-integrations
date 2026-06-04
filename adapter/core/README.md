# Universal Adapter Core

`adapter.core` is the shared contract layer used by connectors, the universal adapter, and EM-safe mods. Provider-specific code depends on these contracts instead of depending directly on MCP handler payloads.

## Table of Contents

- [Scope](#scope)
- [Public Surface](#public-surface)
- [Validation Rules](#validation-rules)
- [Webhook Security](#webhook-security)
- [Sensitive Evidence Screen](#sensitive-evidence-screen)
- [Development](#development)
- [Related Documentation](#related-documentation)

## Scope

The core package defines the neutral object model:

- `Observation` for provider-neutral parsed source material.
- `AdapterEmission` for gateway-bound reviewable output.
- `SourceRef`, `SourceEvidence`, `ConfidenceSurface`, `RoutingHint`, and `AdvisoryResult` for structured evidence and advisory metadata.
- `SourceMode` and `SourceCapabilities` for active, passive, and webhook capability declarations.

Runtime HTTP clients, credential stores, cursor persistence, and gateway materialization stay outside this package.

## Public Surface

| File | Surface | Purpose |
| --- | --- | --- |
| [`observations.py`](observations.py) | `Observation` | Provider-neutral source item before adapter normalization. |
| [`emissions.py`](emissions.py) | `AdapterEmission`, evidence and advisory dataclasses | Gateway-bound reviewable object model. |
| [`pipeline.py`](pipeline.py) | `normalize`, `validate_emissions`, `EmissionContractError` | Shared normalization and contract enforcement. |
| [`capabilities.py`](capabilities.py) | `SourceMode`, `SourceCapabilities` | Declares active, passive, and webhook source support. |
| [`contracts.py`](contracts.py) | `Connector`, `ActiveConnector`, `PollingConnector`, `WebhookConnector` | Protocols implemented by provider connectors. |
| [`sensitive.py`](sensitive.py) | `detect_sensitive`, `SensitiveHit` | Producer-side secret, PHI, and PAN detection. |
| [`webhook_security.py`](webhook_security.py) | `verify_standard_webhook`, `verify_hmac_hex`, `DeliveryDedupCache` | Provider-neutral webhook verification and replay protection. |
| [`filters.py`](filters.py) | `FilterSpec`, `QuotaSpec` | Declarative filter and quota configuration shapes. |
| [`fixtures.py`](fixtures.py) | `FixtureCase` | Test fixture metadata shape. |

## Validation Rules

`validate_emissions` fails closed on the first contract violation. It requires stable source IDs, non-empty evidence, a non-empty adapter version, allowed non-authoritative emission types, and dimensional confidence if confidence is supplied.

`normalize` maps `Observation` objects to `AdapterEmission` objects and immediately validates the result before returning it to callers.

## Webhook Security

`webhook_security.py` provides the shared primitives used by Fathom and Linear:

- `verify_standard_webhook` verifies Standard Webhooks/Svix signatures over raw bytes.
- `verify_hmac_hex` verifies raw-body HMAC-SHA256 hex signatures.
- `DeliveryDedupCache` provides bounded, partitioned TTL replay protection.

Callers must verify before parsing attacker-controlled bodies and mark deliveries seen only after successful verification.

## Sensitive Evidence Screen

The sensitive screen rejects secret, PHI, and payment-card evidence before emissions leave the adapter. Error details use redacted excerpts so credentials are not leaked through validation failures.

## Development

```bash
pytest adapter/core/tests -q
```

Focused test files:

- [`tests/test_pipeline.py`](tests/test_pipeline.py)
- [`tests/test_sensitive.py`](tests/test_sensitive.py)
- [`tests/test_webhook_security.py`](tests/test_webhook_security.py)

## Related Documentation

- [Adapter README](../README.md)
- [Repository README](../../README.md)
- [Feature Index](../../docs/FEATURE_INDEX.md)
- [ADR-0004 Integration Adapter Boundary](../../docs/adr/0004-integration-adapter-boundary.md)
- [ADR-0005 Adapter Emission Contract](../../docs/adr/0005-adapter-emission-contract.md)
