# Connectors

Connectors are provider-facing components. They know provider payload shapes, auth expectations, source IDs, source modes, fixtures, and webhook verification requirements.

Connectors return raw or lightly structured `Observation` objects. The universal adapter turns those observations into validated `AdapterEmission` objects.

## Table of Contents

- [Scope](#scope)
- [Connector Matrix](#connector-matrix)
- [Implementation Pattern](#implementation-pattern)
- [Deferred Runtime Responsibilities](#deferred-runtime-responsibilities)
- [Development](#development)
- [Related Documentation](#related-documentation)

## Scope

Each connector package should contain:

- `connector.py` for provider-specific parsing and capability declarations.
- `auth.md` for expected secret keys and runtime auth notes.
- `fixtures/` for representative provider payloads.
- `tests/` for parsing, normalization, and webhook behavior where implemented.
- `README.md` for the documented contract.

Connectors must not store credentials, own cursor durability, write canonical decisions, or bypass adapter validation.

## Connector Matrix

| Connector | Modes | Implemented | Deferred |
| --- | --- | --- | --- |
| [GitHub](github/README.md) | Active, webhook | Pull-request payload parsing and source-ref handling | Live API fetch and GitHub webhook verification |
| [Fathom](fathom/README.md) | Passive, webhook | Meeting parsing, Svix verification, delivery dedup | Live REST polling and API-key resolution |
| [Linear](linear/README.md) | Webhook, active | Issue webhook parsing, HMAC verification, timestamp replay window, delivery dedup | Live GraphQL fetch and API-key resolution |
| [Granola](granola/README.md) | Passive | Transcript parsing | Live polling, watermark commit, API-key resolution |
| [Google Drive](google_drive/README.md) | Active, passive, webhook | Google Docs URL parsing and `documents.get` body parsing | Live Docs API, OAuth resolution, folder polling, push channels |
| [Local Directory](local_directory/README.md) | Passive | File payload parsing and opaque path token refs | Live directory scan, size caps, extension filters, watermark commit |
| [Jira](jira/README.md) | Planned active and webhook | Auth scaffold and boundary notes | Jira Cloud client, event parsing, dynamic webhook registration |

## Implementation Pattern

A connector should expose a small parse surface, a connector class with `source_id` and `capabilities`, and tests that prove the provider payload normalizes through `adapter.core.normalize`.

The expected shape is:

```python
from adapter.core.pipeline import normalize
from connectors.github.connector import GitHubConnector

connector = GitHubConnector()
observations = connector.observations(payload)
emissions = normalize(observations, adapter_version="dev")
```

## Deferred Runtime Responsibilities

Live IO belongs to the operator runtime unless a specific implementation cycle moves it here with tests and docs:

- API token, OAuth, and keyring resolution.
- HTTP polling and GraphQL calls.
- Cursor and watermark durability.
- Directory scanning.
- Gateway delivery and canonical state writes.

## Development

Run all connector tests:

```bash
pytest connectors -q
```

Run the complete local gate:

```bash
ruff check adapter connectors
mypy adapter connectors
pytest adapter/core/tests connectors -q
```

## Related Documentation

- [Repository README](../README.md)
- [Universal Adapter](../adapter/README.md)
- [Adapter Core](../adapter/core/README.md)
- [Feature Index](../docs/FEATURE_INDEX.md)
- [ADR-0006 Active, Passive, and Webhook Modes](../docs/adr/0006-active-passive-webhook-modes.md)
