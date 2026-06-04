# Linear Connector

The Linear connector maps issue webhook envelopes into provider-neutral `Observation` objects and verifies `Linear-Signature` deliveries before parsing.

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

- Linear issue webhook parsing.
- Preservation of action, type, and organization context in observation metadata.
- Raw-body HMAC-SHA256 verification.
- 60 second timestamp replay window.
- Delivery deduplication when a `DeliveryDedupCache` is injected.
- End-to-end normalization coverage through adapter core.

Deferred:

- Live GraphQL fetch.
- API-key resolution.
- HTTP receiver ownership.

## Modes

| Mode | Status | Notes |
| --- | --- | --- |
| Webhook | Implemented verification and normalization surface | Primary mode because the webhook envelope carries change context. |
| Active | Declared, live fetch deferred | GraphQL fallback belongs to a later implementation cycle. |

## Public Surface

| Symbol | Purpose |
| --- | --- |
| [`parse_event(event)`](connector.py) | Maps a Linear webhook event envelope to an `Observation`. |
| [`LinearConnector`](connector.py) | Declares `source_id = "linear"` and webhook/active capabilities. |
| `LinearConnector.verify(headers, body)` | Verifies HMAC first, then checks the timestamp window; returns `False` on any failure. |
| `LinearConnector.normalize_event(headers, body)` | Re-verifies, deduplicates by `webhookId`, parses JSON, and returns observations. |

## Input and Output

Expected inputs are shaped like:

- [`fixtures/issue_created.json`](fixtures/issue_created.json)
- [`fixtures/webhook_signed.json`](fixtures/webhook_signed.json)

The connector preserves:

- Linear identifier as the source ref.
- Issue URL where present.
- `identifier: title` as the observation title.
- Description as the excerpt, with title and identifier fallback.
- Actor name and creation timestamp.
- `action`, `type`, and `organizationId` in metadata.

## Webhook Verification

Linear verification uses `adapter.core.webhook_security.verify_hmac_hex`.

Verification rules:

- Verify the raw body against `Linear-Signature` before trusting parsed fields.
- Reject missing signatures, empty secrets, malformed JSON, and stale timestamps.
- Enforce a 60 second replay window using `webhookTimestamp`.
- Deduplicate after verification when a dedup cache is supplied.

## Auth and Runtime Boundary

Credential keys and runtime expectations are documented in [`auth.md`](auth.md). Secret resolution and live GraphQL calls stay in the operator runtime.

The connector must not persist credentials, own cursor storage, write canonical decisions, or treat webhook delivery as approval.

## Development

```bash
pytest connectors/linear/tests -q
```

## Related Documentation

- [Connectors](../README.md)
- [Adapter Core Webhook Security](../../adapter/core/README.md#webhook-security)
- [Feature Index](../../docs/FEATURE_INDEX.md)
