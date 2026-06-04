# Fathom Connector

The Fathom connector maps meeting-intelligence payloads into provider-neutral `Observation` objects and verifies Fathom/Svix webhook deliveries before parsing.

## Table of Contents

- [Status](#status)
- [Modes](#modes)
- [Public Surface](#public-surface)
- [Input and Output](#input-and-output)
- [Webhook Verification](#webhook-verification)
- [Auth and Runtime Boundary](#auth-and-runtime-boundary)
- [Development](#development)
- [Related Documentation](#related-documentation)

## Status

Implemented:

- Meeting payload parsing.
- Transcript flattening with summary and title fallback.
- Svix/Standard Webhooks verification through adapter core.
- Delivery deduplication when a `DeliveryDedupCache` is injected.
- End-to-end normalization coverage through adapter core.

Deferred:

- Live REST polling.
- API-key resolution.
- HTTP receiver ownership.

## Modes

| Mode | Status | Notes |
| --- | --- | --- |
| Passive | Declared, parse surface implemented | Runtime `GET /meetings` polling remains deferred. |
| Webhook | Implemented verification and normalization surface | `new-meeting-content-ready` payloads parse through the same meeting shape. |

## Public Surface

| Symbol | Purpose |
| --- | --- |
| [`parse_meeting(meeting)`](connector.py) | Maps a Fathom meeting object to an `Observation`. |
| [`FathomConnector`](connector.py) | Declares `source_id = "fathom"` and passive/webhook capabilities. |
| `FathomConnector.verify(headers, body)` | Verifies Svix signature and freshness; returns `False` on any failure. |
| `FathomConnector.normalize_event(headers, body)` | Re-verifies, deduplicates by `webhook-id`, parses JSON, and returns observations. |

## Input and Output

Expected inputs are shaped like:

- [`fixtures/meeting_content_ready.json`](fixtures/meeting_content_ready.json)
- [`fixtures/webhook_signed.json`](fixtures/webhook_signed.json)

The connector preserves:

- `recording_id` as the stable source ref.
- Share URL or meeting URL where available.
- Meeting title.
- Flattened transcript as the excerpt, with default summary and title fallback.
- Recorder name and recording timestamp.

## Webhook Verification

Fathom webhook verification uses `adapter.core.webhook_security.verify_standard_webhook`.

Verification rules:

- Fail closed on missing or malformed `whsec_` secret.
- Verify the raw request body before parsing JSON.
- Enforce timestamp tolerance.
- Support Svix key rotation signature lists.
- Deduplicate after verification when a dedup cache is supplied.

## Auth and Runtime Boundary

Credential keys and runtime expectations are documented in [`auth.md`](auth.md). Secret resolution and live HTTP polling stay in the operator runtime.

The connector must not persist secrets, own cursor storage, write canonical decisions, or turn webhook delivery into direct authority.

## Development

```bash
pytest connectors/fathom/tests -q
```

## Related Documentation

- [Connectors](../README.md)
- [Adapter Core Webhook Security](../../adapter/core/README.md#webhook-security)
- [Feature Index](../../docs/FEATURE_INDEX.md)
