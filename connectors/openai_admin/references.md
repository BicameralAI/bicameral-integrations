# OpenAI Admin Connector — Canonical References

Single place tracking the canonical documentation links + the verified API contract for the
`openai_admin` connector. See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the
maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | developer-AI / governance |
| Priority | P1 |
| Default trust tier | T1 |
| Integration role | audit-log governance evidence (actor dropped) |
| Readiness (lifecycle) | Beta (audit-event parse, actor identity dropped; proven via `deliver_poll`; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API (audit logs) | https://platform.openai.com/docs/api-reference/audit-logs/list |
| Admin APIs guide | https://developers.openai.com/api/docs/guides/admin-apis |
| Admin/audit help | https://help.openai.com/en/articles/9687866-admin-and-audit-logs-api-for-the-api-platform |
| Auth (admin key) | https://platform.openai.com/docs/api-reference/administration |

## Verified API/webhook contract (as built, 2026-06-05)

- **Endpoint (parsed)**: `GET /v1/organization/audit_logs`. Returns `{data: [event]}`; each event:
  `id`, `effective_at` (unix s), `type` (57 values: `api_key.*`, `login.*`, `logout.*`, `project.*`,
  `role.*`, `user.*`, `invite.*`, `organization.updated`, …), `project` (id/name), `actor`
  (`session{ip_address, user{id,email}}` | `api_key{user{id,email}|service_account{id}}`), + per-type detail.
- **PII control (built)**: the event (type + project + UTC time) is the evidence; the **`actor` is
  structured identity** (`actor.*.user.email`, `actor.session.ip_address`, user ids). FX-SEC-001 screens
  secret/PHI/PAN only (NOT generic email/IP) and `redact()` has no IPv4 scrub — so **actor identity is
  DROPPED at parse, never read** (the sole control). Only the non-PII `actor.type` (`session`/`api_key`,
  allowlisted) is surfaced; the excerpt is `redact()`-ed defensively. `id` → ref; `kind="audit_event"`.
- **Auth (deferred)**: **Admin API key** (`Authorization: Bearer $OPENAI_ADMIN_KEY`; Org-Owner-only;
  admin-only endpoints). Org logging must be enabled in Data Controls (irreversible). Cursor pagination
  (`limit`/`after`/`before`). No live network this cycle.
- **Webhooks**: none (poll-only).

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [OpenAI/Anthropic Admin research brief](../../docs/research-brief-openai-anthropic-admin-2026-06-05.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0012 readiness ladder + runtime boundary](../../docs/adr/0012-connector-readiness-ladder-and-live-ingest-runtime.md)
