# ServiceNow Connector — Canonical References

Single place tracking the canonical documentation links + the verified API contract for the
`servicenow` connector. See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the
maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | ITSM / operations |
| Priority | P2 |
| Default trust tier | T1 |
| Integration role | incident / change evidence (redacted) |
| Readiness (lifecycle) | Beta -> **flip-ready, NOT yet Live** (incident redact-and-pass parse + live fetch-half `build_servicenow_spec`; SSRF-4 URL-injection fixed #133; FX-CFG-001 descriptor shipped). Live flip gated on operator review + a live Table-API poll with a real integration-user credential. |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API (Table API) | https://www.servicenow.com/docs/bundle/zurich-api-reference/page/integrate/inbound-rest/concept/c_TableAPI.html |
| REST auth | https://www.servicenow.com/docs/bundle/zurich-platform-security/page/integrate/authentication/concept/c_RESTAPIAuth.html |
| Incident table | https://www.servicenow.com/docs/bundle/zurich-it-service-management/page/product/incident-management/ |

## Verified API/webhook contract (as built, 2026-06-05)

- **Endpoint (parsed)**: `GET /api/now/table/incident?sysparm_fields=…&sysparm_limit=…&sysparm_offset=…`
  on a per-tenant instance (`https://<instance>.service-now.com`). Incident records carry `number`,
  `short_description`, `description`, `state`, `priority`, `category`, `caller_id`, …
- **Parse + PII**: `parse_incident` excerpt = `redact(short_description — description)` + `(state=…,
  priority=…)`. The free-text `description` is passed through `adapter.core.redaction.redact`
  (**redact-and-pass**: secret/PHI/PAN/email/phone scrubbed; FX-SEC-001 backstop). The **`caller_id` /
  `caller` identity is never read**. `number` → ref; `kind="incident"`.
- **Auth (deferred)**: **Basic** or **OAuth 2.0** via a dedicated integration user with `rest_service` +
  table-read roles (least privilege). `sysparm_*` scope/page the read. No live network this cycle.
- **Webhooks**: none for table reads here (poll-only; outbound is bespoke per-tenant Business Rules).

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [CS/support connectors research brief](../../docs/research-brief-cs-support-connectors-2026-06-04.md) · [PII redaction + Devin/ServiceNow brief](../../docs/research-brief-pii-redaction-devin-servicenow-2026-06-05.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0012 readiness ladder + runtime boundary](../../docs/adr/0012-connector-readiness-ladder-and-live-ingest-runtime.md)
