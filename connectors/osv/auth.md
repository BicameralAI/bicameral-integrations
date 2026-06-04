# OSV Auth

Auth model recorded for the live cycle; this connector ships the **parse
surface** only.

- Default trust tier: T1 (read API) — **no credential** (special case: OSV.dev
  is free and unauthenticated; no rate limit currently published, 32 MiB
  HTTP/1.1 response cap → use `querybatch` + HTTP/2 when the live client lands).
- Auth: none.

## Deferred live paths

- OSV.dev query client: `POST /v1/query` / `POST /v1/querybatch` (by package +
  version, or commit hash) and `GET /v1/vulns/{id}`, driven by an SBOM/lockfile.

No credentials are stored in this package. See [references.md](references.md)
and [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
