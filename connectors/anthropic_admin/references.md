# Anthropic Admin Connector — Canonical References

Single place tracking the canonical documentation links + the verified API contract for the
`anthropic_admin` connector. See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the
maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | developer-AI / governance |
| Priority | P1 |
| Default trust tier | T1 |
| Integration role | usage/cost leverage evidence (aggregate, PII-free) |
| Readiness (lifecycle) | Beta (usage-bucket parse, aggregate; proven via `deliver_poll`; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API (Usage & Cost) | https://platform.claude.com/docs/en/api/usage-cost-api |
| Admin API overview | https://platform.claude.com/docs/en/manage-claude/admin-api |
| Admin API reference | https://platform.claude.com/docs/en/api/admin |
| Auth (admin key) | https://platform.claude.com/settings/admin-keys |

> **Doc-standard attestation (ledger #188, 2026-06-13):** this `references.md` (verified-contract section + provider-docs table + PII handling) + `auth.md` (admin-key model + Privacy/PII section + deferred paths) + `config.json` (explicit `pii_posture` + `wire_gates` + `live_readiness`) assessed against the connector documentation standard — **EXCEEDS minimum**.

## Verified API/webhook contract (as built, 2026-06-05; usage API re-verified live 2026-06-13)

- **Endpoint (parsed)**: `GET /v1/organizations/usage_report/messages` (token usage); companion
  `GET /v1/organizations/cost_report`. Returns time buckets (`bucket_width` `1m`/`1h`/`1d`;
  `starting_at`/`ending_at`) with `results: [{model, workspace_id, api_key_id, service_tier,
  uncached_input_tokens, cache_read_input_tokens, cache_creation: {ephemeral_1h_input_tokens, ephemeral_5m_input_tokens}, output_tokens}]` (verified docs.anthropic 2026-06-08; cache-creation is NESTED, not a flat `cache_creation_input_tokens`).
  `workspace_id`/`api_key_id` may be `null` (default workspace / Workbench).
- **Parse + PII**: `parse_usage` sums input (`uncached`+`cache_read`+`cache_creation`) + output tokens
  and collects distinct models across a bucket. **Aggregate and PII-free** — the opaque
  `workspace_id`/`api_key_id` are NOT surfaced; there is no user email/name in this surface.
  `starting_at` → ref; `kind="usage_metrics"`.
- **Auth (deferred)**: **Admin API key** (`x-api-key: $ANTHROPIC_ADMIN_KEY`, `sk-ant-admin…`,
  admin-role-only) + `anthropic-version: 2023-06-01`. Pagination via `has_more` + `next_page`; poll
  ≤ once/min. No live network this cycle.
- **Webhooks**: none (poll-only).
- **Deferred**: the `/cost_report` rich parse; **per-user** cost via the separate Claude Code Analytics
  API (per-user PII → gated behind the redaction-and-pass model).

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [OpenAI/Anthropic Admin research brief](../../docs/research-brief-openai-anthropic-admin-2026-06-05.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0012 readiness ladder + runtime boundary](../../docs/adr/0012-connector-readiness-ladder-and-live-ingest-runtime.md)
