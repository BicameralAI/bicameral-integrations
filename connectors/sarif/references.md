# SARIF 2.1.0 Connector — Canonical References

Single place tracking the canonical documentation links for the `sarif` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | security/compliance-evidence |
| Priority | P0 |
| Default trust tier | T0 |
| Integration role | static-import evidence |
| Readiness (lifecycle) | Beta (proven end-to-end through the `runtime/` harness against a reference sink; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html |
| Webhook/event | File import only |
| Auth | Not applicable (file ingest) |
| Changelog/notes | https://github.com/oasis-tcs/sarif-spec |

> **Doc-standard attestation (ledger #183, 2026-06-13):** this `references.md` (verified-contract section + provider-docs table + PII handling) + `auth.md` (file-ingest model + deferred paths) + `config.json` (explicit `pii_posture` + `wire_gates` + `live_readiness`) assessed against the connector documentation standard — **EXCEEDS minimum**.

## Verified API/webhook contract (as built, 2026-06-05; SARIF 2.1.0 OASIS schema verified 2026-06-08, frozen standard re-affirmed 2026-06-13)

- **SARIF 2.1.0 report (parsed)**: `parse_sarif` flattens `runs[].results[]` — one Observation per result; `parse_result` reads `{ruleId, level (enum none|note|warning|error), message.text, locations[0].physicalLocation.{artifactLocation.uri, region.startLine}}`; ref is `"{ruleId}@{uri}:{startLine}"`; tool name from `run.tool.driver.name`. (Verified 2026-06-08 against the OASIS SARIF 2.1.0 schema — all paths + the `level` enum confirmed. SARIF 2.1.0 is a FROZEN OASIS standard, re-affirmed 2026-06-13; no version drift possible.)
- **Verification**: no verify — file import (T0); no network delivery, no signature.
- **Auth (deferred)**: none applicable (file ingest); live file-watch/CI-collection path deferred.
- **Modes**: passive only (file import); no webhooks.
- **PII / secret handling**: the SARIF schema carries no *user PII* by design, but a **security-scanner finding `message.text` can quote the very secret it flags** (a secret-scanner emits "Detected AWS key `AKIA…` in `config.py`"). So `message.text` is emitted via **redact-and-pass** — `adapter.core.redaction.redact` scrubs secret/PHI/PAN + email/phone, which is the security-correct choice: emitted RAW, FX-SEC-001 would HARD-REJECT the finding and the security signal would be LOST; redact-and-pass scrubs the secret VALUE and PRESERVES the finding (SG-2026-06-13-E). The connector reads the finding **message** only, **never** the raw code `region.snippet.text` (data minimization); the `ruleId`/`ref` (rule id + repo path) floor is not redacted. Producer sensitive screen (`FX-SEC-001`) remains the fail-closed backstop.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
