# GitHub Copilot Connector — Canonical References

Single place tracking the canonical documentation links + the verified API contract for the
`copilot` connector. See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the
maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | developer-AI tooling |
| Priority | P1 |
| Default trust tier | T1 |
| Integration role | AI-leverage usage evidence (aggregate) |
| Readiness (lifecycle) | Beta (aggregate metrics parse; proven via `deliver_poll`; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API (metrics) | https://docs.github.com/en/rest/copilot/copilot-metrics |
| API (usage metrics, newer) | https://docs.github.com/en/rest/copilot/copilot-usage-metrics |
| Concept | https://docs.github.com/en/copilot/concepts/copilot-usage-metrics/copilot-metrics |
| Auth | https://docs.github.com/en/rest/overview/permissions-required-for-fine-grained-personal-access-tokens |

## Verified API/webhook contract (as built, 2026-06-05)

- **Endpoint (parsed)**: `GET /orgs/{org}/copilot/metrics` (also enterprise/team scopes). Returns a
  daily array of **aggregate, PII-free** objects: `date`, `total_active_users`, `total_engaged_users`,
  and breakdowns `copilot_ide_code_completions` / `copilot_ide_chat` / `copilot_dotcom_chat` /
  `copilot_dotcom_pull_requests` (each with `total_engaged_users` + nested language/editor/model/repo).
- **PII**: none — aggregate counts only, no per-developer identity. `parse_metrics_day` summarizes the
  day's counts; `date` → ref; `kind="usage_metrics"`.
- **Auth (deferred)**: OAuth app token / PAT with `manage_billing:copilot` **or** `read:org` /
  `read:enterprise` (Bearer). Org must enable Copilot metrics. No live network this cycle.
- **Webhooks**: none for this data (poll-only).
- **Deferred**: the newer per-user **NDJSON "usage metrics" report** API (signed download URLs,
  per-user rows → PII) — gated behind the redaction-and-pass model. The legacy Copilot "usage" API was
  closed 2026-04-02 and is not used.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Copilot/Cursor research brief](../../docs/research-brief-copilot-cursor-2026-06-05.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0012 readiness ladder + runtime boundary](../../docs/adr/0012-connector-readiness-ladder-and-live-ingest-runtime.md)
