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

The live registry-fetch path remains **deferred** to the operator runtime (see
[`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its `runtime.deliver_poll` → reference sink path is proven
end-to-end by `runtime/tests/test_runtime.py`, with **zero cross-repo
dependency**. Live (gateway emission) is now operator-actionable — `GatewaySink` is real (bot #109 landed, PR #131); an operator configures it against a real gateway to go Live.

## Surface

- `parse_server(entry)` — registry `server.json` entry → `Observation`
  (`title` or `name` → title; `description` → excerpt, with title/name then a
  `mcp-server` literal as terminal fallback; `name` → ref; `repository.url` or
  `websiteUrl` → ref url; `version`/`repository.source` → `metadata`).
- `McpRegistryConnector` — connector identity and capabilities (`ACTIVE`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
