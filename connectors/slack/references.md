# Slack Connector — Canonical References

Single place tracking the canonical documentation links for the `slack` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | communication |
| Priority | P0 |
| Default trust tier | T2/T3 |
| Integration role | notification-first, ingest later |
| Readiness (lifecycle) | Beta (parse + signature verify, proven end-to-end through the `runtime/` harness; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://docs.slack.dev/apis/web-api/ |
| Webhook/event | https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks |
| Auth | https://docs.slack.dev/authentication/ |
| Changelog/notes | https://docs.slack.dev/changelog/ |

## Verified API/webhook contract (as built, 2026-06-05)

- **Message / event_callback (parsed)**: `parse_message` reads `{event.{type, channel, ts, text, user, message.{ts, channel, text, user}}}`; unwraps `message_changed`-style edit subtypes via inner `message` dict; excerpt is `text` falling back to `"(no text) {channel}:{ts}"`.
- **Verification (built)**: `X-Slack-Signature: v0=<hex HMAC-SHA256(signing_secret, "v0:{ts}:{raw_body}")>` with `X-Slack-Request-Timestamp` (5-minute replay window); `verify()` calls `verify_slack_signature` (fail-closed, constant-time). `url_verification` handshake dropped (signed but produces no Observations). Dedup on `event_id`.
- **Auth (deferred)**: signing secret + OAuth bot token resolved by operator runtime; live Events API receipt deferred. No live network this cycle.
- **Modes**: webhook only (Events API); no active/passive modes declared.
- **PII handling**: message text, channel id, and user id emitted; display names not read. Producer sensitive screen (`FX-SEC-001`) is the guard.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
