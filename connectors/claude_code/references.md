# Claude Code Connector — Canonical References

Single place tracking the canonical documentation links for the `claude-code` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | source-control / developer-AI tooling |
| Priority | P0 |
| Default trust tier | T0 (local file import) |
| Integration role | developer-AI session evidence + provenance |
| Readiness (lifecycle) | Beta (proven end-to-end through the `runtime/` harness against a reference sink; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| Data storage / retention | https://code.claude.com/docs/en/data-usage |
| `.claude` directory | https://code.claude.com/docs/en/claude-directory |
| Settings (attribution / cleanupPeriodDays) | https://code.claude.com/docs/en/settings |
| Webhook/event | None — local JSONL files |
| Auth | None (local file) |
| Changelog/notes | https://code.claude.com/docs |

## Verified API/webhook contract (as built, 2026-06-05)

- **Session-line record (parsed)**: `parse_session_line` reads one JSONL line dict; only `type` values in `{"user", "assistant", "summary"}` produce an Observation — all other types (e.g. `mode`, `attachment`, `file-history-snapshot`, `last-prompt`, unknown future kinds) return `None` (skipped, not errored). Key fields: `uuid`/`sessionId` (ref), `timestamp` (ISO string), `message.content` (text or block list), `message.model`, `cwd`.
- **Verification**: no verify — passive file import; no network delivery, no signature.
- **Auth (deferred)**: none (T0 local file import); reads `~/.claude/projects/<slug>/<session-id>.jsonl` the operator already has on disk. Live file-watch and `history.jsonl` paths deferred.
- **Modes**: passive only; no webhooks.
- **PII handling**: transcripts are plaintext and may contain file contents, command stdout/stderr, and pasted text (potential secrets/PII). This connector performs no redaction; the producer sensitive screen (`FX-SEC-001`) is the in-pipeline guard.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
