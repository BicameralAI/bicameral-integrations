# Zendesk Connector — Canonical References

Single place tracking the canonical documentation links for the `zendesk` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | support / customer-success |
| Priority | P1 |
| Default trust tier | T1/T5 |
| Integration role | support-ticket / customer evidence |
| Readiness (lifecycle) | Beta (parse + Base64-HMAC webhook verify, proven end-to-end through the `runtime/` harness; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://developer.zendesk.com/api-reference/ticketing/introduction/ |
| Webhook/event | https://developer.zendesk.com/documentation/webhooks/ |
| Webhook verify | https://developer.zendesk.com/documentation/webhooks/verifying/ |
| Auth | https://developer.zendesk.com/api-reference/introduction/security-and-auth/ |

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [CS/support connectors research brief](../../docs/research-brief-cs-support-connectors-2026-06-04.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0012 readiness ladder + runtime boundary](../../docs/adr/0012-connector-readiness-ladder-and-live-ingest-runtime.md)
