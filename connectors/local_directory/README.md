# Local-Directory Connector

The local-directory connector maps file payloads from a watched directory into provider-neutral `Observation` objects.

## Table of Contents

- [Status](#status)
- [Modes](#modes)
- [Public Surface](#public-surface)
- [Input and Output](#input-and-output)
- [Runtime Boundary](#runtime-boundary)
- [Development](#development)
- [Related Documentation](#related-documentation)

## Status

Implemented:

- `{path, content, modified}` payload parsing.
- Stable opaque source refs derived from a path hash.
- Filename-stem title fallback.
- End-to-end normalization coverage through adapter core.

Deferred:

- Live directory scanning.
- Extension filters and file size caps.
- Watermark two-phase commit.

## Modes

| Mode | Status | Notes |
| --- | --- | --- |
| Passive | Declared, parse surface implemented | Runtime scanning remains outside this package. |

## Public Surface

| Symbol | Purpose |
| --- | --- |
| [`parse_file(payload)`](connector.py) | Maps a local file payload to an `Observation`. |
| [`LocalDirectoryConnector`](connector.py) | Declares `source_id = "local_directory"` and passive capability. |
| `LocalDirectoryConnector.observations(payload)` | Returns one parsed observation for a file payload. |

## Input and Output

Expected input is shaped like [`fixtures/note.json`](fixtures/note.json).

The connector preserves:

- Opaque `local-<sha256-prefix>` ref derived from the path.
- File content as the excerpt, falling back to filename stem.
- Filename stem as title.
- Optional source type label as kind, defaulting to `planning`.
- Modified timestamp where supplied.

The path hash prevents leaking an operator filesystem path into downstream refs.

## Runtime Boundary

The operator runtime owns directory watching, file reads, extension filtering, size caps, and watermark persistence.

The connector must not read arbitrary files on its own, persist state, write decisions, or bypass adapter validation.

## Development

```bash
pytest connectors/local_directory/tests -q
```

## Related Documentation

- [Connectors](../README.md)
- [Adapter Core](../../adapter/core/README.md)
- [Feature Index](../../docs/FEATURE_INDEX.md)
