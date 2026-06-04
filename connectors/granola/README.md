# Granola Connector

The Granola connector maps meeting transcript payloads into provider-neutral `Observation` objects.

## Table of Contents

- [Status](#status)
- [Modes](#modes)
- [Public Surface](#public-surface)
- [Input and Output](#input-and-output)
- [Auth and Runtime Boundary](#auth-and-runtime-boundary)
- [Development](#development)
- [Related Documentation](#related-documentation)

## Status

Implemented:

- Transcript payload parsing.
- Participant-name extraction.
- Stable transcript source refs.
- End-to-end normalization coverage through adapter core.

Deferred:

- Live HTTP polling.
- Watermark two-phase commit.
- API-key resolution.

## Modes

| Mode | Status | Notes |
| --- | --- | --- |
| Passive | Declared, parse surface implemented | Runtime polling remains outside this package. |

## Public Surface

| Symbol | Purpose |
| --- | --- |
| [`parse_transcript(item)`](connector.py) | Maps a Granola transcript item to an `Observation`. |
| [`GranolaConnector`](connector.py) | Declares `source_id = "granola"` and passive capability. |
| `GranolaConnector.observations(payload)` | Returns one parsed observation for a transcript payload. |

## Input and Output

Expected input is shaped like [`fixtures/transcript.json`](fixtures/transcript.json).

The connector preserves:

- Transcript ID as the source ref.
- Transcript text as the excerpt, falling back to title.
- Meeting title.
- First participant name where available.
- `ended_at` as the timestamp.

## Auth and Runtime Boundary

Credential keys and runtime expectations are documented in [`auth.md`](auth.md). Polling, cursor durability, and API-key resolution stay in the operator runtime.

The connector must not persist secrets, scan sources directly, write decisions, or skip adapter validation.

## Development

```bash
pytest connectors/granola/tests -q
```

## Related Documentation

- [Connectors](../README.md)
- [Adapter Core](../../adapter/core/README.md)
- [Feature Index](../../docs/FEATURE_INDEX.md)
