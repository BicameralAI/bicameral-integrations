# Project Backlog

## Blockers (Must Fix Before Progress)

### Security Blockers

<!-- Format: - [ ] [S#] Description -->

### Development Blockers

<!-- Format: - [ ] [D#] Description -->

## Backlog (Planned Work)

<!-- Format: - [ ] [B#] Description -->
- [x] [B1] SHA-pin the legacy workflows `.github/workflows/ci.yml` (`actions/checkout@v6.0.3`, `setup-python@v6.2.0`) and `secret-scan.yml` (`actions/checkout@v6.0.3`, `trufflehog@v3.95.5`) — Complete (security-queue remediation, 2026-06-04; closes Scorecard PinnedDependencies on ci.yml/secret-scan.yml).
- [x] [B2] **SPDX header backfill + gate flip** — Complete 2026-07-08: 103 files backfilled (69 in the CI scan set + 34 in mods/tests/protocol), `check_license_headers.py` now exits 1 on a miss, and the quality.yml job is renamed "SPDX headers (blocking)" with the scan widened to `adapter connectors runtime scripts mods tests protocol`.
- [ ] [B3] Ecosystem governance rollout: port the governance-integrity gate + compliance mappings to `bicameral-bot`/`bicameral-mcp`/`bicameral-cloud`; evaluate AGT as a `bicameral-bot` sidecar (operator request, 2026-06-04).
- [ ] [B4] Enable repo Dependency Graph (admin) to flip `dependency-review` from advisory to blocking.
- [ ] [B5] **Branch protection on `main`** (admin): require PR + passing status checks (CI, Security Scan, Governance Gate) + ≥1 approval. Resolves Scorecard `Branch-Protection` + `Code-Review`. Needs repo-admin (current token is push-only).
- [x] [B6] **OpenSSF Scorecard `startup_failure` on `main`** — Complete (2026-06-04, **two iterations**; SG-2026-06-04-O). **Real root cause** (found by RUNNING, after a first reasoned fix failed): `_reusable-scorecard.yml` declared top-level **`permissions: read-all`**, which exceeds the caller `scorecard.yml`'s grant (`contents: read` + `security-events: write`) — GitHub rejects a reusable workflow requesting broader permissions than its caller, hence `startup_failure`. Fix: mirror the working `_reusable-codeql.yml` permission pattern (reusable top `contents: read`; job `contents/security-events: write/actions: read`; caller grants the same). The first iteration (drop `id-token` + `publish_results: false`) was kept (no public-badge need, no OIDC) but was NOT the cause. No admin needed.
- [x] [B13] **Scorecard Token-Permissions hardening** — Complete (2026-06-04). Findings #21-24 (HIGH) fixed: `codeql.yml`/`scorecard.yml`/`sbom.yml` moved their write scopes to the **calling-job level** with top-level `permissions: contents: read`; `_reusable-sbom.yml` dropped the unneeded `contents: write` → `contents: read` (its steps need `id-token`/`attestations`, not contents). Pattern PR-verified on CodeQL (pull_request trigger) before trusting it on the push-only Scorecard (SG-2026-06-04-O). Stale CodeQL **#17** dismissed via API (false-positive — fixed in `2a81142`); accepted Pinned-Dependencies **#18-20** dismissed via API (won't-fix, stdlib-only-runtime rationale). Remaining: only #13/#1 (Code-Review, Branch-Protection) which need **branch protection on `main`** (B5, repo-admin).
- [x] [B15] **Vendored v1 ingest schema drift-recheck** — Closed 2026-07-08 as **superseded-by-removal** (#226): the bot published the v2 `ExternalIngestEnvelope` and the migration spec pins `/api/v1/ingest` as local/MCP-actor only, so the v1 mapping + vendored schema were REMOVED rather than re-pinned. The v2 schema is vendored byte-exact (`runtime/schemas/external_ingest_request_v2.schema.json` @ bot schema commit `5c24c60f`) with emitter-discipline conformance + forbidden-authority-disjointness tests in `runtime/tests/test_gateway_mapping.py`.
- [x] [B14] **Parse-surface non-dict nested-field hardening** — Closed 2026-07-08. Verification: `parse_pull_request` was ALREADY guarded (`_d` coercion helper, connectors/github/connector.py:35-38, red-team Cycle B #56); the one live residual was notion `parse_page` `created_by` (present-but-non-dict → AttributeError) — fixed with an isinstance floor + regression test (`test_parse_page_non_dict_created_by_floors`).
- [ ] [B12] **SBOM workflow OIDC twin** (surfaced by the Scorecard-gate audit, N1): `_reusable-sbom.yml`/`sbom.yml` request the same `id-token: write` (+ `attestations: write`) for build provenance. SBOM triggers only on `release`/`workflow_dispatch` and has never run, so it is not currently red — but it will `startup_failure` on the first release under the same OIDC-refusal cause. Decide before v0: either repo-admin enables Actions OIDC, or drop attestation/provenance to keep the SBOM gate green. Ties to release-trust posture (bot #73).
- [x] [B7] **Devin / Devin Desktop connector — value-add research** — Complete (2026-06-04, `docs/research-brief-devin-2026-06-04.md`). Verdict: meets the bar via the **Devin v3 REST API** (read-only sessions/messages, poll); Desktop/Local has no documented file artifact. Catalogued **P1, ACTIVE/T1**, evidence-adapter (launch/steer → `bicameral-mcp`). Build deferred behind Claude Code (P0) — tracked as **B9**.
- [x] [B9] **Devin connector build** (P1) (2026-06-05, Entry #79, `connectors/devin`): read-only Devin v3 sessions API → Observations; `parse_session`; free-text passed through the redaction-and-pass model (`redact()`); live polling + RBAC service-user token + `/messages` surface deferred.
- [x] [B8] **PagerDuty signature first-party spot-check** — Confirmed 2026-07-08 in a real browser (the doc moved to `developer.pagerduty.com/docs/verifying-webhook-signatures`; old slug 404s). First-party page confirms the implemented scheme exactly: `X-PagerDuty-Signature` comma-separated multi-sig (`v1=` + HMAC-SHA256 hex over the raw body; rotation support; any-match; constant-time compare). `connectors/pagerduty/auth.md` updated with the citation.
- [x] [B10] **Connector module-docstring freshness pass** — Complete 2026-07-08: pagerduty + fathom module docstrings no longer claim `verify()` is deferred (both are implemented — multi-sig membership and Svix respectively); sentry was verified already-current. Doc-only, no logic change.
- [x] [B11] **Align connector `verify()` exception catches** — Closed 2026-07-08 as ALREADY DONE: `FathomConnector.verify` catches `(WebhookVerificationError, AttributeError, TypeError)` (connectors/fathom/connector.py:119, red-team Cycle B #57) — the backlog entry pre-dated that fix and was stale.

## Security posture dispositions (Scorecard checks — recorded, not code-fixable)

- **Pinned-Dependencies (pip):** dev toolchain (ruff/mypy/pytest/bandit/pip-audit/codespell/pyyaml) is version-pinned but not hash-pinned. **Accept** — stdlib-only runtime, no shipped deps; revisit if a hash-locked manifest is adopted.
- **Maintained:** transient (repo < 90 days); ages out automatically. **Dismiss (won't fix).**
- **SAST:** already satisfied by CodeQL + Bandit on PR/push; low score is historical backfill. **Dismiss (control exists).**
- **Fuzzing:** N/A — pure provider-payload parse library, no untrusted-byte parser surface. **Dismiss (won't fix).**
- **CII-Best-Practices:** opt-in OpenSSF badge enrollment; pursue only if the badge is wanted. **Accept.**

## Wishlist (Nice to Have)

<!-- Format: - [ ] [W#] Description -->

---
_Updated by /qor-* commands automatically_

## Security red-team findings (2026-06-05, GH #50-#61)

Adversarial review of the connector/adapter/runtime code. Cores sound (no signature
forgery; redact-and-pass invariant held; GatewaySink 201-only + F-1 re-screen). Findings:

- [x] [#52] FX-SEC-001 screen now covers `source_id`/`source_ref.url`/`ref` (secret-in-URL→gateway leak) — Cycle A, Entry #86.
- [x] [#53] PAN/PHI no longer leak verbatim into `EmissionContractError` (`_redact_excerpt` masks all classes) — Cycle A, Entry #86.
- [x] [#54] `GatewaySink` rejects CR/LF token/headers + token-free catch-all — Cycle A, Entry #86.
- [x] [#50] (Cycle B, Entry #88) ReDoS — confluence `_TAG_RE` `<[^>]+>` quadratic (Cycle B).
- [x] [#51] (Cycle B, Entry #88) ReDoS — redaction `_EMAIL_RE` quadratic, via `redact()` (Cycle B).
- [x] [#55] (Cycle B, Entry #88) Huge-int JSON literal (>4300 digits) crashes `normalize_event` (ValueError uncaught) (Cycle B).
- [x] [#56] (Cycle B, Entry #88) Type-confusion AttributeError escapes `normalize_event`/`observations` (github base/user; servicenow strip) (Cycle B).
- [x] [#57] (Cycle B, Entry #88) fathom `verify()` narrow `except` → malformed input crashes vs fail-closed (Cycle B).
- [x] [#58] (Cycle B, Entry #88) cursor leaks generic email/phone (`day`/`mostUsedModel` unfiltered) (Cycle B — needs an email/phone screen pattern decision).
- [x] [#59] (Cycle B, Entry #88) `observations()` crashes on non-dict payload (all 26, no `isinstance` guard) (Cycle B).
- [x] [#60] (Cycle C, Entry #90) Replay defeatable for windowless providers (id-less/eviction/TTL) (Cycle C).
- [x] [#61] (Cycle C, Entry #90) Nits: zero-width passes excerpt check; `source_id` no length bound (Cycle C).
