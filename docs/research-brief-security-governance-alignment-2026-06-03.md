# Research Brief

**Date**: 2026-06-03
**Analyst**: The Qor-logic Analyst
**Target**: Security & governance standards alignment across the three BicameralAI repos — `bicameral-mcp` (Python, standards-bearer), `bicameral-bot` (Rust, gateway/governance core), `bicameral-integrations` (Python, ours).
**Scope**: Ingest input-security, authority-boundary enforcement, webhook/secrets handling, CI security/governance gates, ledger integrity, scaffold completeness. Grounded in actual source; every finding cites file:line.

---

## Executive Summary

`bicameral-mcp` is the mature standard — four layered ingest guards (size / rate / prompt-injection canary / sensitive-data), hard-vs-soft gating with DLQ, webhook HMAC + dedup, keyring secrets, and a deep CI gate set. **Neither `bicameral-bot` nor `bicameral-integrations` inherits that standard yet, and two gaps are critical.** (1) The bot's external-facing gateway has *no* input-security guards and — more seriously — *no actor-authority enforcement* on its review/dashboard routes, so the "edges can't write canonical" doctrine our entire integration architecture depends on is **prose-only, not code-enforced** (`routes.rs`). (2) The three repos run **three different secret scanners**, and ours (`gitleaks-action@v2`) is the one mcp explicitly rejected as paid-license-gated for orgs. We (integrations) also ship **no test/lint CI** at all. None of this blocks our current PR #1, but it must be closed before live external connectors point at the gateway.

## The Standard (bicameral-mcp baseline)

### Security
- **Four ingest guards** (`handlers/ingest.py`): `_check_payload_size` (`:138`→`size_limit_exceeded`), `_check_rate_limit` (`:202`, token bucket `:167-193`→`rate_limit_exceeded`), `_check_canary` (`:231`, catalog `canary_patterns.py:52-84`→`injection_canary_match`), `_check_sensitive` (`:265`, secret/PHI/PAN catalog `sensitive_patterns.py:60-106`→`sensitive_data:<cls>`).
- **Hard vs soft gating** (`:83-91`): `sensitive_data:*` + `malformed_payload` are HARD (fail-fast both modes); size/rate/canary are SOFT (DLQ in passive). DLQ at `dlq/store.py:83+`, mode-0600 JSONL + sidecar.
- **Webhook security**: HMAC-SHA256 constant-time verify (`webhooks/github.py:48-72`), three-way channel match for Drive (`webhooks/google_drive.py:61-133`), replay dedup cache 24h TTL (`webhooks/dedup.py:51-145`).
- **Secrets**: OS keyring with whitelist + 8 KiB cap + audit lifecycle, never emits values (`secrets_store/store.py:46-182`).
- **CI**: **TruffleHog** `--only-verified` (`secret-scan.yml`); explicitly notes gitleaks-action is *paid-license for orgs*. Plus `lint-and-typecheck.yml` (ruff + mypy + format-history gate), `test-mcp-regression.yml`, `perf-gate.yml`, `preflight-eval.yml`, `pr-body-refs-lint.yml`.
- **SECURITY.md** (disclosure SLA, supported versions, in/out-of-scope threats) + `docs/policies/threat-model-and-trust-boundary.md`, `audit-log.md` (forbid-list of content keys, dual-write resilience).

### Governance
- META_LEDGER SHA256 phase-artifact chain; CLAUDE.md mandatory tool-change↔skill-update coupling; sociable-testing doctrine; 2 ADRs; FEATURE_INDEX / SHADOW_GENOME.

## Per-Repo Alignment Matrix

| Standard (mcp) | bicameral-bot | bicameral-integrations (ours) |
|---|---|---|
| Ingest size limit | ❌ absent (no `DefaultBodyLimit`, `routes.rs`/`lib.rs:72-88`) | ➖ n/a (producer side; emits, doesn't receive) |
| Ingest rate limit | ❌ absent; `preflight.rs` rate-limit is text not code | ➖ n/a |
| Prompt-injection canary | ❌ absent | ⚠️ none on emitted content |
| Sensitive-data gate (HARD) | ❌ absent (snapshot_content unscanned) | ⚠️ `validate_emissions` enforces contract but does **not** screen secrets/PII |
| Authority boundary **enforced in code** | ❌ **review/dashboard routes accept state mutations with no actor identity** (`routes.rs:265,616`) | ✅ producer is non-authoritative by construction; `validate_emissions` rejects canonical fields |
| Webhook HMAC + dedup | ➖ (no webhooks) | ⚠️ deferred — must port mcp's when connectors go live |
| Secret-scan tool | custom `scripts/secret_scan.py` | **`gitleaks-action@v2`** — the paid-license-for-orgs tool mcp rejected |
| Test/lint CI gate | ✅ `rust.yml` (fmt/clippy -D warnings/test) | ❌ **none** — only `secret-scan.yml`; pytest/ruff/mypy run locally only |
| SECURITY.md / GOVERNANCE.md | ❌ neither | ✅ both present |
| META_LEDGER machine-verifiable | ❌ prose hashes, no CI check | ❌ prose hashes; `qor-logic verify-ledger` skips our 6 entries as "non-verifiable markup" |
| Scaffold completeness | — | ⚠️ missing `docs/SYSTEM_STATE.md`, `docs/GOVERNANCE_INDEX.md` (governance-health MISSING) |

## Findings (prioritized)

### CRIT-1 — Bot gateway has no input-security guards on an external-facing ingest
`crates/bicameral-gateway/src/routes.rs` `ingest_candidate` has only an `EmptyEvidence` gate (`:112`); `lib.rs:72-88` wires **zero middleware** (no `DefaultBodyLimit`, no `tower_governor`, no timeout/CORS). PR #95 relaxed the contract and published a schema inviting external producers **without** inheriting any of mcp's four guards. For an endpoint whose purpose is untrusted Jira/Slack/email/transcript content, the absent **sensitive-data HARD gate** is the worst: credentials/PII in a pasted Slack message would be materialized into the candidate store. (Previously raised against PR #95.)

### CRIT-2 — Bot's authority boundary is doctrine-only, not code-enforced (NEW, most severe)
ADR-0007 and CONTEXT.md (`:112`) state edges/connectors/UI "must not create Decisions directly." But the gateway **does not enforce this**:
- `POST /api/v1/review` (`routes.rs:265`) accepts any `ReviewCommand` with **no actor identity, capability check, or state-transition validation** — an unauthenticated POST can approve / reject / escalate any candidate.
- `POST /api/v1/dashboard/command` (`routes.rs:616`) routes `accept_candidate` / `approve_signoff` etc.; the actor is the hardcoded/spoofable string `"dashboard"` (`:709`). An external POST can **promote candidates to canonical Decisions and approve signoff**.
- No auth anywhere (`lib.rs:45-52` only *warns* on non-loopback bind).

This is the single largest hole across all three repos, and it directly undermines the invariant our integrations work is built on: we carefully keep producers non-authoritative, but the gateway will accept canonical mutations from anyone who can reach it. **The edge being honest is worthless if the core doesn't enforce the boundary.**

### CRIT-3 — Secret-scan fragmentation; ours is the license-broken tool
mcp = TruffleHog `--only-verified`; bot = custom `scripts/secret_scan.py`; **integrations = `gitleaks/gitleaks-action@v2`** (`.github/workflows/secret-scan.yml`, `.pre-commit-config.yaml`). mcp's own `secret-scan.yml` header documents that gitleaks-action "requires a paid license for organizations" — so under the `BicameralAI` org our scan is likely failing or unlicensed, and it diverges from the standard. Three tools = three coverage profiles = inconsistent assurance.

### HIGH-1 — Integrations ships no test/lint CI
Only `secret-scan.yml` exists. Our 14 tests + ruff + mypy run **locally only**; nothing gates a PR. mcp enforces `lint-and-typecheck.yml`; bot enforces `rust.yml` clippy `-D warnings`. PR #1 has no automated quality gate.

### HIGH-2 — Live connectors must inherit mcp's webhook + secret discipline
Our `WebhookConnector` protocol exists but verification/dedup are deferred. When we implement live connectors we must port mcp's HMAC verify + `DeliveryDedupCache` (`webhooks/*.py`, `dedup.py`) and should add producer-side sensitive-data screening (defense-in-depth, especially while CRIT-1 stands). Do not reinvent.

### MED-1 — META_LEDGER not machine-verifiable in any repo
All three use prose hash blocks; `qor-logic verify-ledger` skipped our entries. No CI hash-chain check anywhere. Governance is narrative, not tamper-evident.

### MED-2 — Integrations missing scaffold governance artifacts
`governance-health --profile skill-entry`: `docs/SYSTEM_STATE.md` and `docs/GOVERNANCE_INDEX.md` MISSING (scaffold-owned; seedable).

### MED-3 — Bot missing SECURITY.md / GOVERNANCE.md
No disclosure policy or formal threat model doc (ironically, ours has both; mcp has SECURITY.md). The most security-critical repo has the least published security policy.

## Blueprint Alignment

| Blueprint claim (our docs) | Actual finding | Status |
|---|---|---|
| "Governance and materialization remain outside this repository… bot gateway is the only path to canonical" (ARCHITECTURE_PLAN:47-48, ADR-0001) | Bot gateway enforces no auth/authority on review/dashboard routes (`routes.rs:265,616`) | **DRIFT (critical)** — the boundary we rely on isn't enforced upstream |
| ADR-0005 "canonical state not an adapter-owned field" + non-authoritative producers | Our `validate_emissions` enforces this on our side | **MATCH (ours)** |
| Bot owns the contract + schema discipline (ADR-0002:63; our D2) | PR #95 publishes `protocol/schemas/v1/` via schemars (schema-as-truth) but ships no negative/forbidden-authority fixtures | **PARTIAL** — discipline started, enforcement fixtures missing |
| Repo inherits secret-scanning (secret-scan.yml present) | Uses gitleaks-action (paid-license for orgs per mcp) vs standard TruffleHog | **DRIFT** |
| Quality gates run in CI | Integrations has no test/lint CI | **DRIFT** |

## Recommendations

### What WE (integrations) do to align — P0/P1
1. **[P0] Swap secret scanner to TruffleHog** (match mcp's `secret-scan.yml` + drop gitleaks-action's org license problem). Update `.pre-commit-config.yaml` too. *(small, mechanical)*
2. **[P0] Add a `ci.yml` test/lint gate** — `pytest adapter/core/tests connectors/github/tests`, `ruff check`, `mypy adapter/core connectors/github` on PRs to `main`. Mirror mcp's `lint-and-typecheck.yml` posture. PR #1 should not merge without this.
3. **[P1] Producer-side sensitive screening** — extend the pipeline with an optional pre-emit secret/PII screen (port the *interface* of mcp's `_check_sensitive`) so we never forward credentials to the gateway — defense-in-depth while CRIT-1 stands.
4. **[P1] Seed `SYSTEM_STATE.md` + `GOVERNANCE_INDEX.md`** (`qor-logic seed`) to clear the governance-health MISSING findings.
5. **[P1] When live connectors land**, port mcp's webhook HMAC + `DeliveryDedupCache` verbatim (HIGH-2); add the negative/forbidden-authority conformance fixtures (our #93 precedent #5) to the integrations conformance test.

### Cross-repo (raise as bot issues — not ours to fix, but ours to flag)
6. **[P0] Bot CRIT-2** — enforce actor authority on `review` + `dashboard/command` routes (reject canonical mutations without authenticated/capability-checked actor). This is a security issue, not a feature gap; recommend filing against `bicameral-bot` with high severity.
7. **[P0] Bot CRIT-1** — add `DefaultBodyLimit` + rate-limit middleware + port the sensitive-data HARD gate to the gateway before external producers connect (folds into the PR #95 review already noted).
8. **[P1] Standardize secret-scan on TruffleHog across all three repos**; standardize a CI META_LEDGER hash-chain check.

## Updated Knowledge

New verified facts for `docs/SHADOW_GENOME.md`: (a) the bot gateway's authority boundary is doctrine-only — review/dashboard routes accept canonical mutations with a spoofable actor (CRIT-2); (b) the three repos use three different, inconsistent secret scanners, and ours is the org-license-broken one (CRIT-3); (c) mcp is the inheritance baseline — its four ingest guards + webhook HMAC/dedup + DLQ are the standard sibling repos must adopt, not re-derive.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
