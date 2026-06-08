# Confluence Connector — Canonical References

Single place tracking the canonical documentation links + the verified API contract for the
`confluence` connector. See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the
maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | documentation / knowledge |
| Priority | P1 |
| Default trust tier | T1/T3 |
| Integration role | document evidence |
| Readiness (lifecycle) | Beta (parse of REST content storage body; verify deferred; proven via `deliver_poll`; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API (Cloud REST v2) | https://developer.atlassian.com/cloud/confluence/rest/v2/ |
| Webhook/event | https://developer.atlassian.com/cloud/confluence/using-webhooks/ |
| Auth | https://developer.atlassian.com/cloud/confluence/security-overview/ |
| Data Center webhooks (HMAC) | https://confluence.atlassian.com/doc/managing-webhooks-1021225606.html |

## Verified API/webhook contract (as built, 2026-06-05)

- **Content shape (parsed)**: REST content object `{id, type, title, body: {storage: {value,
  representation}}, _links: {base, webui}}`. `parse_content` flattens the XHTML `body.storage.value`
  to text (lossy `_strip_storage_html` — tag strip + entity unescape + whitespace collapse, **not a
  sanitizer**); `id` → ref; `_links.base + _links.webui` → url; `kind="page"`.
- **Verification (DEFERRED — corrected rationale, verified 2026-06-08)**: Confluence **Cloud**
  webhooks DO carry a verifiable scheme, but it is **Connect-app JWT** (`Authorization: JWT <token>`,
  **HS256** over the per-tenant install shared secret, with a `qsh` request binding) — NOT an HMAC
  payload signature. The Data-Center/Server HMAC `X-Hub-Signature` does not transfer to Cloud. The
  earlier "no confirmable signature scheme" claim was too strong. `verify()` stays deferred for the
  correct reason: the JWT path needs a registered Connect app + the install-handshake shared-secret
  store + a JWT/qsh verifier (`verify_hmac_hex` over the raw body is the wrong primitive), so it is
  built only when an operator runs a Connect app. The connector is proven through the poll/active path.
- **Active fetch (deferred)**: `GET /wiki/rest/api/content/{id}?expand=body.storage`; OAuth 2.0 (3LO)
  or API-token Basic; Connect-app JWT (`qsh`). No live network this cycle.
- **Events** (when webhook lands): `page_created` / `page_updated` / `page_deleted`.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0012 readiness ladder + runtime boundary](../../docs/adr/0012-connector-readiness-ladder-and-live-ingest-runtime.md)
