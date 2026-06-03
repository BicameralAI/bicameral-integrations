# Google Drive Auth

Credentials are declared here but stored by the core operator runtime, not in
repository-local config.

Expected credential material:

- OAuth token JSON
- refresh token when granted

Expected scopes:

- `https://www.googleapis.com/auth/documents.readonly`
- `https://www.googleapis.com/auth/drive.metadata.readonly`

