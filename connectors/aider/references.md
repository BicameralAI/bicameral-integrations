# Aider Connector — Canonical References

Single place tracking the canonical documentation links for the `aider` connector.
See [INTEGRATION_DOCS_INDEX](../../docs/INTEGRATION_DOCS_INDEX.md) for the maintained provider-docs table and refresh cadence.

## This connector

| Field | Value |
|---|---|
| Catalog category | source-control / developer-AI tooling |
| Priority | P1 |
| Default trust tier | T0 |
| Integration role | evidence + provenance (developer-AI commits) |
| Readiness (lifecycle) | Beta (proven end-to-end through the `runtime/` harness against a reference sink; ADR-0012) |

## Provider documentation (verify on refresh)

| Kind | Link |
|---|---|
| Git attribution | https://aider.chat/docs/git.html |
| Config / options | https://aider.chat/docs/config/options.html |
| Analytics (deferred) | https://aider.chat/docs/more/analytics.html |
| Webhook/event | No public read API/webhook; git commits + local files |
| Auth | Not applicable (git/file import) |
| Changelog/notes | https://aider.chat/HISTORY.html · https://github.com/Aider-AI/aider |

> **Doc-standard attestation (ledger #175, 2026-06-13):** this `references.md` (verified-contract section + provider-docs table + PII handling) + `auth.md` (git-attribution scheme + deferred live paths) + `config.json` (explicit `pii_posture` + `wire_gates` + `live_readiness`) assessed against the connector documentation standard — **EXCEEDS minimum**.

## Verified API/webhook contract (as built, 2026-06-05; attribution re-verified live 2026-06-13)

- **Commit record (parsed)**: `parse_commit` reads `{hash, message, author_name, committer_name, authored_at, trailers}`; attribution channel detected by `_attributed_by` — `"author"` when `"(aider)"` in `author_name`, `"committer"` when in `committer_name`, `"co-author"` when a `Co-authored-by:` trailer contains `"aider"`.
- **Verification**: no verify — poll/passive (git import; no network delivery, no signature).
- **Auth (deferred)**: none applicable (T0 git/file import); live git-log walk, `--analytics-log` JSONL, and `.aider.chat.history.md` transcript paths all deferred.
- **Modes**: passive only; no webhooks exist for this source.
- **PII handling**: the commit **subject** is emitted via **redact-and-pass** — `adapter.core.redaction.redact` scrubs secret/PHI/PAN + email/phone to placeholders (F3 / SG-2026-06-13-A: a developer may paste a token/email into a commit message). The git **author name is RETAINED** (`author_name`, e.g. `"Dev Example (aider)"`) as the intentional T0 provenance signal — this connector exists to attribute developer-AI work, the deliberate opposite of the fathom/claude_code name-drop (F4 / SG-2026-06-13-B); only `author_name` is read, never `author_email`. The commit-hash floor is opaque and un-redacted. Producer sensitive screen (`FX-SEC-001`) remains the fail-closed backstop for secret/PHI/PAN.

## Canonical governance references

These apply to every Bicameral connector (see also the connector's own README/auth.md):

- [Governed Adapter Contract](../../docs/GOVERNED_ADAPTER_CONTRACT.md)
- [Trust Tier Model](../../docs/TRUST_TIER_MODEL.md)
- [Data Classification & Redaction](../../docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- [Integration Strategy & Candidate Harvesting](../../docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md)
- [Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md)
- [Integration Docs Index](../../docs/INTEGRATION_DOCS_INDEX.md)
- ADRs: [0008 evidence-adapters-not-authorities](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md) · [0009 trust-tiered-governance](../../docs/adr/0009-trust-tiered-integration-governance.md) · [0010 product-agnostic-harvesting](../../docs/adr/0010-product-agnostic-candidate-harvesting.md) · [0004 adapter boundary](../../docs/adr/0004-integration-adapter-boundary.md) · [0005 emission contract](../../docs/adr/0005-adapter-emission-contract.md) · [0006 active/passive/webhook modes](../../docs/adr/0006-active-passive-webhook-modes.md)
