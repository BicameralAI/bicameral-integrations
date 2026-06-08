# Google Drive Auth

Credentials are declared here but stored by the core operator runtime, not in
repository-local config.

Expected credential material:

- OAuth token JSON
- refresh token when granted

Expected scopes (verified 2026-06-08, developers.google.com/docs/api):

- `https://www.googleapis.com/auth/documents.readonly` — valid for `documents.get`.
- `https://www.googleapis.com/auth/drive.readonly` (or `drive.file`) — for Drive access.
  **NOTE (drift corrected):** `drive.metadata.readonly` is **NOT** an accepted scope for the Docs
  `documents.get` call (the official authorization-scopes list is `documents`, `documents.readonly`,
  `drive`, `drive.readonly`, `drive.file`); use `drive.readonly`/`drive.file` for the live fetch.
  (`drive.metadata.readonly` is valid only for the separate Drive `files.get` metadata path.)

