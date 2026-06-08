# MCP Registry Connector

Read-only MCP Registry evidence adapter: parses a `server.json` entry into a
neutral `Observation` for scoring and allowlist decisions. **Status: Beta**
(ADR-0012; catalog mcp/agent-ecosystem, priority P0, default trust tier T1). A
Phase-1 foundation candidate from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Active** — an MCP Registry `server.json` entry maps to one neutral
  `Observation` (`parse_server`). Read-only evidence for scoring and allowlist
  decisions; no canonical-state writes (ADR-0008).

The live HTTP poll runs in the operator runtime via the built, fixture-proven
`build_mcp_registry_spec` (see [`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Graduated from Candidate → **Beta** (2026-06-08) against the **verified public contract**
(registry.modelcontextprotocol.io/openapi.yaml): the **no-auth** `GET /v0/servers` list, with
entries wrapped under `servers` → `element.server` (unwrapped by the spec), and cursor
pagination (`cursor` → `metadata.nextCursor`, no has-more). `build_mcp_registry_spec` uses
`NoAuth` + `PageToken(token_field="metadata.nextCursor", has_more_field=None)`, proven end-to-end
through the `runtime/` poll harness against recorded fixtures (the operator supplies the live
transport). Live (gateway emission) is operator-actionable — `GatewaySink` is real (bot #109, PR #131).

## Surface

- `parse_server(entry)` — registry `server.json` entry → `Observation`
  (`title` or `name` → title; `description` → excerpt, with title/name then a
  `mcp-server` literal as terminal fallback; `name` → ref; `repository.url` or
  `websiteUrl` → ref url; `version`/`repository.source` → `metadata`).
- `McpRegistryConnector` — connector identity and capabilities (`ACTIVE`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (public, no-auth reads): [auth.md](auth.md)
