# Local-Directory Connector

Read-only evidence adapter: captures decisions dropped as files in a watched
local directory. **Status: Beta** (ADR-0012).

## Modes

- **Passive** — the operator runtime scans a configured directory for new files
  (by extension, size-capped, watermarked by mtime) and hands each file to this
  connector as a `{path, content, modified}` payload; `parse_file` maps it to a
  neutral `Observation`.

The live directory scan, watermark two-phase commit, size caps, and extension
filtering remain **deferred** to the operator runtime (see [`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its `runtime.deliver_poll` → reference sink path is proven
end-to-end by `runtime/tests/test_runtime.py`, with **zero cross-repo
dependency**. Live (gateway emission) remains gated on bicameral-bot #109.

## Surface

- `parse_file(payload)` — `{path, content, modified}` → `Observation` (content
  → excerpt with stem fallback; filename stem → title; sha256 path token → ref;
  `modified` → timestamp).
- `LocalDirectoryConnector` — connector identity and capabilities (`PASSIVE`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
