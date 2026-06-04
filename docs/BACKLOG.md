# Project Backlog

## Blockers (Must Fix Before Progress)

### Security Blockers

<!-- Format: - [ ] [S#] Description -->

### Development Blockers

<!-- Format: - [ ] [D#] Description -->

## Backlog (Planned Work)

<!-- Format: - [ ] [B#] Description -->
- [x] [B1] SHA-pin the legacy workflows `.github/workflows/ci.yml` (`actions/checkout@v6.0.3`, `setup-python@v6.2.0`) and `secret-scan.yml` (`actions/checkout@v6.0.3`, `trufflehog@v3.95.5`) — Complete (security-queue remediation, 2026-06-04; closes Scorecard PinnedDependencies on ci.yml/secret-scan.yml).
- [ ] [B2] Backfill SPDX license headers across all `.py` files, then flip the `license-headers` gate from advisory to blocking.
- [ ] [B3] Ecosystem governance rollout: port the governance-integrity gate + compliance mappings to `bicameral-bot`/`bicameral-mcp`/`bicameral-cloud`; evaluate AGT as a `bicameral-bot` sidecar (operator request, 2026-06-04).
- [ ] [B4] Enable repo Dependency Graph (admin) to flip `dependency-review` from advisory to blocking.
- [ ] [B5] **Branch protection on `main`** (admin): require PR + passing status checks (CI, Security Scan, Governance Gate) + ≥1 approval. Resolves Scorecard `Branch-Protection` + `Code-Review`. Needs repo-admin (current token is push-only).
- [ ] [B6] **OpenSSF Scorecard `startup_failure` on `main`** (admin): every Scorecard run fails at startup — almost certainly the repo's default Actions workflow-token permission is read-only, blocking Scorecard's `security-events: write`. Set default workflow permissions to allow `security-events: write` (Settings → Actions → Workflow permissions). Until fixed, Scorecard cannot re-evaluate/auto-close PinnedDependencies alerts (the action-pin fixes in Entry #37 were dismissed as resolved-stale). Needs repo-admin.
- [x] [B7] **Devin / Devin Desktop connector — value-add research** — Complete (2026-06-04, `docs/research-brief-devin-2026-06-04.md`). Verdict: meets the bar via the **Devin v3 REST API** (read-only sessions/messages, poll); Desktop/Local has no documented file artifact. Catalogued **P1, ACTIVE/T1**, evidence-adapter (launch/steer → `bicameral-mcp`). Build deferred behind Claude Code (P0) — tracked as **B9**.
- [ ] [B9] **Devin connector build** (P1): governed cycle for the read-only Devin v3 sessions/messages API → Observations (parse surface; live polling + RBAC service-user token deferred). Pin to v3; mandatory message-body redaction.
- [ ] [B8] **PagerDuty signature first-party spot-check**: confirm `developer.pagerduty.com/docs/verifying-signatures` (JS-rendered) in a browser before relying on the `X-PagerDuty-Signature` multi-sig verifier in production. Scheme cross-verified (support docs + third parties), implemented fail-closed in Entry #44.

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
