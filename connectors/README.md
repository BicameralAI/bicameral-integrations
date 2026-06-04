# Connectors

Connectors are provider-facing components. They know external APIs, auth flows,
pagination, retries, webhook signatures, and provider-native ids.

Each connector exposes a small **parse surface** — one or more
`parse_*(payload) -> Observation` functions plus a `<Provider>Connector` class
declaring its `source_id` and supported modes. Connectors return raw or lightly
structured provider observations; the [universal adapter](../adapter/README.md)
turns those observations into Bicameral emissions via `pipeline.normalize()`.
Connectors are read-only evidence adapters — they never write canonical state
(ADR-0008).

Live network, auth, and webhook-signature paths are deferred per connector and
documented in each connector's `auth.md`; the implemented surface this cycle is
payload parsing, exercised against synthetic fixtures.

## Index

| Connector | Status | Modes | Surface |
|---|---|---|---|
| [github](github/) | Prototype | active, webhook | `parse_pull_request` |
| [fathom](fathom/) | Prototype | passive, webhook | `parse_meeting` |
| [linear](linear/) | Prototype | webhook, active | `parse_event` |
| [granola](granola/) | Prototype | passive | `parse_transcript` |
| [local_directory](local_directory/) | Prototype | passive | `parse_file` |
| [google_drive](google_drive/) | Prototype | active | `parse_document` |
| [sarif](sarif/) | Prototype | passive | `parse_sarif` / `parse_result` |
| [slack](slack/) | Prototype | webhook | `parse_message` |
| [notion](notion/) | Prototype | active, webhook | `parse_page` |
| [mcp_registry](mcp_registry/) | Prototype | active | `parse_server` |
| [jira](jira/) | Candidate | — | scaffold (not yet implemented) |

Candidate selection and trust tiers are tracked in the
[Integration Candidate Catalog](../docs/INTEGRATION_CANDIDATE_CATALOG.md) and the
[Trust Tier Model](../docs/TRUST_TIER_MODEL.md).
