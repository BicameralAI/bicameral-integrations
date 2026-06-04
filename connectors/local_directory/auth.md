# Local-Directory Auth

No network credentials. This is a local filesystem source: the operator
runtime reads files from a configured directory path and owns all access
control via the host filesystem permissions.

Operator-runtime concerns deferred from this parse surface:

- Non-recursive `iterdir()`; hidden files and subdirectories ignored.
- Extension allow-list (default `.md`, `.txt`, `.json`).
- File-size cap (default 1 MiB); oversized files skipped, not ingested.
- Watermark by latest mtime with two-phase commit.
- Path tokens are sha256-derived so the ledger never carries the operator's
  home-directory layout.
