# Devin Connector — Canonical References

Single place tracking the canonical documentation links + the verified API contract for the
`devin` connector. See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the
maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | developer-AI / agentic coding |
| Priority | P1 |
| Default trust tier | T1 |
| Integration role | agentic-session evidence (redacted) |
| Readiness (lifecycle) | Beta (session parse, free-text redacted; proven via `deliver_poll`; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API overview | https://docs.devin.ai/api-reference/overview |
| API auth | https://docs.devin.ai/api-reference/authentication |
| Sessions (list) | https://docs.devinenterprise.com/api-reference/v3/sessions/organizations-sessions |
| Session messages | https://docs.devin.ai/api-reference/v3/sessions/get-enterprise-session-messages |

## Verified API/webhook contract (as built, 2026-06-05)

- **Endpoint (parsed)**: `GET /v3/organizations/{org}/sessions` (list); base `https://api.devin.ai/v3/`.
  Session objects carry `session_id` (`devin-…`), `title`, `status`, `structured_output`, `pull_request.url`.
- **Parse + PII**: `parse_session` excerpt = `redact("[status] title: structured_output")` — the session
  free-text (title / structured_output / message trail) may carry secrets/PII, so it is passed through
  `adapter.core.redaction.redact` (redact-and-pass; FX-SEC-001 backstop). `pull_request.url` is kept as the
  **artifact location** (github/gitlab/jira precedent); author/user identity is not read. `kind="session"`.
- **Auth (deferred)**: **Bearer** — Service-User API key (`cog_…`, shown once, RBAC-scoped) or PAT
  ("coming soon"). No live network this cycle.
- **Webhooks**: none (poll-only).
- **Deferred**: the `GET /v3/enterprise/sessions/{devin_id}/messages` per-message trail (richer surface);
  the Desktop/Local path has no documented file artifact (API is the evidence path; launch/steer =
  `bicameral-mcp`, SG-K).

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Devin research brief](../../docs/research-brief-devin-2026-06-04.md) · [PII redaction + Devin/ServiceNow brief](../../docs/research-brief-pii-redaction-devin-servicenow-2026-06-05.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0012 readiness ladder + runtime boundary](../../docs/adr/0012-connector-readiness-ladder-and-live-ingest-runtime.md)
