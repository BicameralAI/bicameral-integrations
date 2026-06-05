# GitHub Connector — Canonical References

Single place tracking the canonical documentation links for the `github` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | source-control |
| Priority | P0 |
| Default trust tier | T1/T3 |
| Integration role | evidence + event |
| Readiness (lifecycle) | Beta (parse + `X-Hub-Signature-256` HMAC verify, proven end-to-end through the `runtime/` harness; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://docs.github.com/en/rest |
| Webhook/event | https://docs.github.com/en/webhooks |
| Auth | https://docs.github.com/en/apps/oauth-apps |
| Changelog/notes | https://docs.github.com/en/rest/overview/api-versions |

## Verified API/webhook contract (as built, 2026-06-05)

- **Pull-request payload (parsed)**: `parse_pull_request` reads a flat PR object — `{number, title, body, html_url, base.repo.full_name, user.login, merged_at}`; excerpt is `body` falling back to `title`. `normalize_event` unwraps the webhook envelope (`{action, number, pull_request, repository}`) injecting the top-level `number` into the nested PR dict before parsing.
- **Verification (built)**: `X-Hub-Signature-256: sha256=<hex HMAC-SHA256(secret, raw_body)>`; `verify()` strips `"sha256="` prefix and calls `verify_hmac_hex` (fail-closed, constant-time). Dedup on `X-GitHub-Delivery` header GUID.
- **Auth (deferred)**: `api_key` + `webhook_secret` resolved by operator runtime (keyring). Live REST fetch deferred; no live network this cycle.
- **Modes**: active (REST) + webhook (`pull_request` event); both share `parse_pull_request`.
- **PII handling**: PR body and title emitted; `user.login` (not display name) as author. Producer sensitive screen (`FX-SEC-001`) is the guard.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
