# Universal Adapter

The universal adapter converts provider-neutral connector observations into validated `AdapterEmission` objects with preserved source evidence.

Provider-specific behavior belongs in [`connectors/`](../connectors/README.md). The adapter owns the shared contracts, validation rules, sensitive-data screen, fixture helpers, filters, webhook primitives, and normalization pipeline.

## Table of Contents

- [Scope](#scope)
- [Package Map](#package-map)
- [Data Flow](#data-flow)
- [Contract Rules](#contract-rules)
- [Development](#development)
- [Related Documentation](#related-documentation)

## Scope

This package is Bicameral-facing. It accepts observations that have already been parsed by provider connectors and emits reviewable objects for the downstream gateway.

The adapter must not fetch provider APIs, resolve credentials, write canonical decisions, approve signoff, or own durable event storage.

## Package Map

| Path | Purpose |
| --- | --- |
| [`core/`](core/README.md) | Neutral object model, validation, normalization, filters, sensitive screen, and webhook security helpers. |
| [`__init__.py`](__init__.py) | Package marker for adapter imports. |

## Data Flow

```text
connector payload parser
        |
        v
adapter.core.Observation
        |
        v
adapter.core.normalize(...)
        |
        v
adapter.core.AdapterEmission
        |
        v
bicameral-bot gateway review path
```

## Contract Rules

The adapter core enforces the ADR-0005 emission contract:

- `source_id` must be stable and limited to `A-Za-z0-9._-`.
- Each emission must include at least one non-empty evidence excerpt.
- `adapter_version` must be recorded.
- `emission_type` must remain non-authoritative: `candidate`, `evidence`, `hint`, or `advisory`.
- Confidence, when present, must remain dimensional rather than a single opaque score.
- Secret, PHI, and payment-card evidence is rejected before gateway handoff.

## Development

Run the adapter test surface:

```bash
pytest adapter/core/tests -q
```

Run the full local gate before opening a PR:

```bash
ruff check adapter connectors
mypy adapter connectors
pytest adapter/core/tests connectors -q
```

## Related Documentation

- [Repository README](../README.md)
- [Adapter Core](core/README.md)
- [Connectors](../connectors/README.md)
- [Feature Index](../docs/FEATURE_INDEX.md)
- [Architecture Decisions](../docs/adr/)
