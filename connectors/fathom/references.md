# Fathom Connector — Canonical References

Single place tracking the canonical documentation links for the `fathom` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | meetings/transcripts |
| Priority | P3 |
| Default trust tier | T1/T5 |
| Integration role | evidence + event |
| Readiness (lifecycle) | Beta -> **flip-ready, NOT yet Live** (parse + Svix verify; transcript/summary/title redact-and-passed, speaker + recorder real names dropped; FX-CFG-001 descriptor shipped; contract re-verified live 2026-06-12). Webhook receipt + REST poll operator-runtime; live network deferred (ADR-0012). |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://developers.fathom.ai/ |
| Webhook/event | https://developers.fathom.ai/webhooks |
| Auth | API key (`X-Api-Key`); Standard-Webhooks/Svix-style signing |
| Changelog/notes | https://developers.fathom.ai/ |

## Verified API/webhook contract (re-verified live 2026-06-12)

- **Meeting payload (parsed)**: `parse_meeting` reads `{recording_id, meeting_title/title, transcript[].text, default_summary.markdown_formatted, share_url/url, recorded_by.name, recording_end_time/created_at}`; transcript flattened as **bare spoken-text** lines (the `transcript[].speaker.display_name` real name is DROPPED — SG-2026-06-12-H); excerpt = redact(transcript) → redact(summary) → redact(title). All fields re-verified verbatim against developers.fathom.ai (2026-06-12).
- **Verification (built)**: `webhook-id`, `webhook-timestamp` (epoch seconds), `webhook-signature` (`v1,<b64>`). `verify()` calls `verify_standard_webhook`: `HMAC-SHA256(base64decode(whsec_… secret), "{id}.{timestamp}.{body}")`, base64, constant-time compare. Dedup on `webhook-id`. Replay window now **Fathom-documented as 5 minutes**. (Fathom does not name "Svix"; the brand is inferred from the byte-identical scheme.)
- **Auth (deferred)**: REST passive poll uses the API key as the **`X-Api-Key`** header (`GET https://api.fathom.ai/external/v1/meetings`, cursor pagination, transcript/summary opt-in expansions); keyring resolution stays in operator runtime. No live network this cycle.
- **Modes**: passive (REST poll) + webhook (`new-meeting-content-ready`); both share `parse_meeting`.
- **PII handling**: transcript + summary + title **redact-and-passed** (secret/PHI/PAN + email/phone scrubbed); speaker + recorder **real names dropped**; `FX-SEC-001` hard-screens secret/PHI/PAN as the un-bypassable backstop.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
