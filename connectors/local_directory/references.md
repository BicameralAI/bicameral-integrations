# Local Directory Connector — Canonical References

Single place tracking the canonical documentation links for the `local_directory` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | file/static-import |
| Priority | P-internal |
| Default trust tier | T0 |
| Integration role | evidence |
| Readiness (lifecycle) | Beta (proven end-to-end through the `runtime/` harness against a reference sink; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| API | Local filesystem (no provider API) |
| Webhook/event | n/a |
| Auth | No network credentials (host filesystem permissions) |
| Changelog/notes | n/a |

> **Doc-standard attestation (ledger #175, 2026-06-13):** this `references.md` (verified-contract section + provider-docs table + PII handling) + `auth.md` (no-credential filesystem model + deferred operator-runtime concerns) + `config.json` (explicit `pii_posture` + `wire_gates` + `live_readiness`) assessed against the connector documentation standard — **EXCEEDS minimum**.

## Verified API/webhook contract (as built, 2026-06-05; flip re-verified 2026-06-13)

- **File payload (parsed)**: `parse_file` reads `{path, content, modified, source_type_label}`; ref is `"local-{sha256(path)[:16]}"` (stable, opaque — operator filesystem layout never stored in the ledger); excerpt is the **redact-and-passed** file content, falling back to the redacted filename stem then the opaque path token.
- **Verification**: no verify — local filesystem import; no network delivery, no signature.
- **Auth (deferred)**: none (no network credentials); host filesystem permissions are the access control. Live directory scan, extension allow-list, 1 MiB size cap, and watermark two-phase commit are deferred to the operator runtime.
- **Modes**: passive only; no webhooks.
- **PII handling**: file content + the filename stem are emitted via **redact-and-pass** — `adapter.core.redaction.redact` scrubs secret/PHI/PAN + email/phone to placeholders before emission (SG-2026-06-13-A: a local/passive source still needs redaction parity; no network boundary is not no PII boundary). The path is sha256-tokenized into an opaque ref (no FS-layout leak). The operator additionally owns extension/size filtering and directory scoping. Producer sensitive screen (`FX-SEC-001`) remains the fail-closed backstop for secret/PHI/PAN.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
