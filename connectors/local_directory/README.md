# Local-Directory Connector

Captures decisions dropped as files in a watched local directory.

## Modes

- **Passive** — the operator runtime scans a configured directory for new files
  (by extension, size-capped, watermarked by mtime) and hands each file to this
  connector as a `{path, content, modified}` payload; `parse_file` maps it to a
  neutral `Observation`.

The live directory scan, watermark two-phase commit, size caps, and extension
filtering stay in the operator runtime (see `auth.md`); this connector is the
parse surface only.

## Surface

- `parse_file(payload)` — `{path, content, modified}` → `Observation` (content
  → excerpt with stem fallback; filename stem → title; sha256 path token → ref;
  `modified` → timestamp).
- `LocalDirectoryConnector` — connector identity and capabilities (`PASSIVE`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
