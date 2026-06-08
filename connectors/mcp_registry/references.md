# MCP Registry Connector — Canonical References

Single place tracking the canonical documentation links for the `mcp_registry` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | mcp/agent-ecosystem |
| Priority | P0 |
| Default trust tier | T1 |
| Integration role | read-only scoring/allowlist |
| Readiness (lifecycle) | Beta (proven end-to-end through the `runtime/` harness against a reference sink; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API (OpenAPI) | https://registry.modelcontextprotocol.io/openapi.yaml |
| API (reference) | https://github.com/modelcontextprotocol/registry (docs/reference/api, server-json) |
| Webhook/event | none (poll only) |
| Auth | **public — no auth on reads** (`GET /v0/servers`); auth only on publish/POST |
| Changelog/notes | https://github.com/modelcontextprotocol/registry/releases |

## Verified API contract (doc-confirmed 2026-06-08, registry.modelcontextprotocol.io/openapi.yaml)

- **Endpoint**: public `GET /v0/servers` (also `/v0.1/servers`, the docs-canonical current path); no auth on reads. Cursor pagination — request `cursor` (+ optional `limit`, default 30/max 100); response token `metadata.nextCursor` (no has-more; stop on absent).
- **Envelope**: list under top-level `servers`; each entry is `{server: {ServerJSON}, _meta}`. The runtime spec unwraps `element.server` before `parse_server`.
- **Server entry (parsed)**: `parse_server` reads `{name, title, description, repository.{url, source}, websiteUrl, version}` from `element.server`; ref is `name` or `title`; excerpt is `description` falling back to `title`/`name`; metadata carries `version` and `repository_source`. (Registry status lives under `element._meta`; not surfaced this cycle.)
- **Verification**: no verify — public poll; no webhook delivery, no signature.
- **Modes**: active only (read-only scoring/allowlist); no webhooks.
- **PII handling**: server metadata (name, description, repo URL) emitted; no user PII in the registry schema.
- **Drift corrected (was 2026-06-05)**: prior docs said "GitHub/auth depending on usage" + "live fetch deferred / Candidate" — the registry now has a defined public contract (graduated to Beta with the verified live list path).

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
