# MCP Registry Connector

Provider-facing MCP Registry adapter. **Status: Prototype** (catalog
mcp/agent-ecosystem, priority P0, default trust tier T1). A Phase-1 foundation
candidate from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Active** — an MCP Registry `server.json` entry maps to one neutral
  `Observation` (`parse_server`). Read-only evidence for scoring and allowlist
  decisions; no canonical-state writes (ADR-0008).

The live registry-fetch path is deferred this cycle (see [`auth.md`](auth.md));
this connector is the parse surface only.

## Surface

- `parse_server(entry)` — registry `server.json` entry → `Observation`
  (`title` or `name` → title; `description` → excerpt, with title/name then a
  `mcp-server` literal as terminal fallback; `name` → ref; `repository.url` or
  `websiteUrl` → ref url; `version`/`repository.source` → `metadata`).
- `McpRegistryConnector` — connector identity and capabilities (`ACTIVE`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
