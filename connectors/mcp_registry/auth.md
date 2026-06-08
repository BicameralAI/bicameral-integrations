# MCP Registry Auth

Stage: **Beta** (graduated from Candidate 2026-06-08 against the verified contract below).

- Default trust tier: T1 (read).
- **Auth: NONE for reads (verified)**. `registry.modelcontextprotocol.io/openapi.yaml`
  (2026-06-08) — the list path `GET /v0/servers` (also `/v0.1/servers`, the docs-canonical
  current path) has **no `security` block**: public, unauthenticated. Authentication is
  required only for **publish** (`POST`), out of scope for this read-only connector. The
  runtime poll spec uses `NoAuth` accordingly.

## Live path — reference poll client (contract verified 2026-06-08)

`build_mcp_registry_spec` (`runtime/poll_specs.py`) is built + recorded-fixture-proven:

- **Endpoint**: `GET https://registry.modelcontextprotocol.io/v0/servers` (public, no auth).
- **Envelope**: list under top-level **`servers`**; each entry is `{server: {ServerJSON}, _meta}`
  — the spec unwraps **`element.server`** before parse (name/title/description/repository/
  websiteUrl/version live under `server`, NOT at the element top level). Registry status
  (`isLatest`, etc.) lives under `element._meta` and is not surfaced this cycle.
- **Pagination**: request param **`cursor`** (+ optional `limit`, default 30/max 100); response
  token at **`metadata.nextCursor`** (camelCase, nested); **no has-more** field — stop when
  `nextCursor` is absent/empty/null (wired via `PageToken(token_field="metadata.nextCursor",
  has_more_field=None)`).

The live HTTP poll itself stays in the operator runtime (the harness supplies the fetch seam).
See [references.md](references.md) and [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
