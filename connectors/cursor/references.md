# Cursor Connector — Canonical References

Single place tracking the canonical documentation links + the verified API contract for the
`cursor` connector. See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the
maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | developer-AI tooling |
| Priority | P1 |
| Default trust tier | T1 |
| Integration role | AI-leverage usage evidence |
| Readiness (lifecycle) | Beta (aggregate usage parse, PII-dropped; proven via `deliver_poll`; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API (Admin) | https://cursor.com/docs/account/teams/admin-api |
| API overview | https://cursor.com/docs/api |
| Analytics API | https://cursor.com/docs/account/teams/analytics-api |
| Auth | https://cursor.com/docs/account/teams/admin-api (Basic; API key as username) |

## Verified API/webhook contract (as built, 2026-06-05)

- **Endpoint (parsed)**: `POST /teams/daily-usage-data` (date range; poll ≤ hourly). Returns per-user-day
  rows: `userId`, `day`, `email`, `name`, `isActive`, `acceptedLinesAdded`, `totalAccepts`/`totalApplies`/
  `totalRejects`, `totalTabsShown`/`Accepted`, `composerRequests`/`chatRequests`/`agentRequests`,
  `mostUsedModel`, `clientVersion`, …
- **PII control (built)**: **every row carries `email` (PII)**; FX-SEC-001 screens secret/PHI/PAN only
  (NOT generic email — SG-2026-06-05-A). `parse_usage_day` reads a strict numeric+model allowlist and
  **never reads `email` / `name` / `clientVersion`**. **Per-developer attribution uses the OPAQUE integer
  `userId`** (SG-2026-06-05-D supersedes -A for userId only — pseudonymous; identity never emitted).
- **Auth (deferred)**: HTTP **Basic with the API key as the username, empty password** (`-u KEY:`);
  team-admin-issued key. No live network this cycle.
- **Webhooks**: none (poll-only, ≤ once/hour).
- **Companion endpoints**: `GET /teams/members`, `POST /teams/spend` (PII-dense — deferred).

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Copilot/Cursor research brief](../../docs/research-brief-copilot-cursor-2026-06-05.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0012 readiness ladder + runtime boundary](../../docs/adr/0012-connector-readiness-ladder-and-live-ingest-runtime.md)
