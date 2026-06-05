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
| API | https://github.com/modelcontextprotocol/registry |
| Webhook/event | Registry metadata + repo updates |
| Auth | GitHub/auth model depending on usage |
| Changelog/notes | https://github.com/modelcontextprotocol/registry/releases |

## Verified API/webhook contract (as built, 2026-06-05)

- **Server entry (parsed)**: `parse_server` reads `{name, title, description, repository.{url, source}, websiteUrl, version}`; ref is `name` or `title`; excerpt is `description` falling back to `title`/`name`; metadata carries `version` and `repository_source`.
- **Verification**: no verify — active poll/import; no webhook delivery, no signature.
- **Auth (deferred)**: GitHub/auth model depending on usage; live registry fetch deferred. No live network this cycle.
- **Modes**: active only (read-only scoring/allowlist); no webhooks.
- **PII handling**: server metadata (name, description, repo URL) emitted; no user PII in the registry schema.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
