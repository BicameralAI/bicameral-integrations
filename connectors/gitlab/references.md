# GitLab Connector — Canonical References

Single place tracking the canonical documentation links + the verified API/webhook contract
for the `gitlab` connector. See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md)
for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | source-control |
| Priority | P1 |
| Default trust tier | T1/T3 |
| Integration role | evidence + event |
| Readiness (lifecycle) | Beta (parse + plaintext `X-Gitlab-Token` verify, proven end-to-end through the `runtime/` harness; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://docs.gitlab.com/ee/api/ |
| Webhook/event | https://docs.gitlab.com/user/project/integrations/webhooks/ |
| Webhook verify (token) | https://docs.gitlab.com/user/project/integrations/webhooks/#validate-payloads-by-using-a-secret-token |
| Auth | https://docs.gitlab.com/ee/api/rest/authentication.html |

## Verified API/webhook contract (as built, 2026-06-05)

- **Webhook events**: `Merge Request Hook` / `Issue Hook`; the event kind is in the payload
  `object_kind` (`"merge_request"` / `"issue"`) and the `X-Gitlab-Event` header. Event fields live
  under `object_attributes` (`iid`, `title`, `description`, `url`, `action`); `project.path_with_namespace`
  identifies the project; `user.username` is the actor.
- **Verification (built)**: a **plaintext shared-secret token** in the `X-Gitlab-Token` header — GitLab
  does **NOT** HMAC-sign the body. `verify()` constant-time-compares it to the configured secret
  (`adapter.core.webhook_security.verify_shared_token`), fail-closed. Per-event dedup on `X-Gitlab-Event-UUID`.
- **Deferred (stronger path)**: a newer **Standard-Webhooks signing token** produces an HMAC-SHA256
  signature over `webhook-id.webhook-timestamp.body` (`webhook-signature` headers) — the same Svix scheme
  `connectors/fathom` implements via `verify_standard_webhook`; not wired this cycle.
- **Active fetch (deferred)**: REST poll of merge requests / issues (same `object_attributes` shape);
  personal/project/group access token. No live network this cycle.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0012 readiness ladder + runtime boundary](../../docs/adr/0012-connector-readiness-ladder-and-live-ingest-runtime.md)
