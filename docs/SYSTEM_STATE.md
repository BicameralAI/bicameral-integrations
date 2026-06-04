# System State

## Snapshot Metadata

| Attribute | Value |
|-----------|-------|
| **Last Updated** | 2026-06-04 |
| **Updated By** | Orchestrator (qor-auto-dev-1) |
| **Phase** | MERGED to `main` — Phase-2 connectors + security-queue remediation landed; docs refreshed each cycle close |
| **Iteration** | 13 governed cycles (adapter seam + GitHub; secret screen + CI; 5 connectors; L3 webhook verify; CI governance/security gate ecosystem; 4 Phase-1 parse surfaces + doc pass; Continue + Aider; reusable-workflow gate templates; AGT-sidecar evaluation; connector value-add research + surface-selection doctrine; **security-queue remediation**; **Phase-2 connectors OSV/Sentry/PagerDuty**) |
| **Session Seal** | `b5ebb27c` (META_LEDGER Entry #51 chain hash) |

---

## File Tree (Current Reality)

```
bicameral-integrations/
|-- adapter/
|   `-- core/  (emissions, observations, contracts, capabilities, pipeline,
|              sensitive, webhook_security, filters, fixtures, __init__ + tests/)
|-- connectors/  (each: connector.py, __init__, README, auth.md, fixtures/, tests/)
|   |-- github/         (PR -> Observation; ACTIVE+WEBHOOK)
|   |-- fathom/         (meeting -> Observation; PASSIVE+WEBHOOK)
|   |-- linear/         (webhook event -> Observation; WEBHOOK+ACTIVE)
|   |-- granola/        (transcript -> Observation; PASSIVE)
|   |-- local_directory/(file -> Observation; PASSIVE)
|   |-- google_drive/   (document -> Observation; ACTIVE)
|   |-- sarif/          (SARIF result -> Observation; PASSIVE; T0)
|   |-- slack/          (message event -> Observation; WEBHOOK; T2)
|   |-- notion/         (page -> Observation; ACTIVE+WEBHOOK; T1)
|   |-- mcp_registry/   (server.json -> Observation; ACTIVE; T1)
|   |-- continue_dev/   (dev-data event -> Observation; PASSIVE; T0)
|   |-- aider/          (git commit -> Observation; PASSIVE; T0)
|   |-- osv/            (vulnerability record -> Observation; ACTIVE; T1 no-auth)
|   |-- sentry/         (issue webhook -> Observation; WEBHOOK; T1)
|   |-- pagerduty/      (incident webhook -> Observation; WEBHOOK; T1)
|   `-- jira/           (scaffold — Candidate, no connector.py yet)
|-- mods/  (structure under active build by Codex — not edited by this track)
|-- scripts/  (governance_gate.py + check_license_headers.py + tests/)
|-- docs/  (CONCEPT, ARCHITECTURE_PLAN, META_LEDGER, SHADOW_GENOME, SYSTEM_STATE,
|          GOVERNANCE_INDEX, BACKLOG, FEATURE_INDEX, adr/, compliance/, ecosystem/, research-brief-*)
|-- .github/workflows/  (10 gate workflows: ci, governance-gate, codeql, dependency-review,
|          scorecard, sbom, secret-scan, security-scan, quality, pr-hygiene
|          + 6 reusable `_reusable-*.yml` workflow_call templates)
`-- (LICENSE, README, CONTRIBUTING, SECURITY, GOVERNANCE, CODE_OF_CONDUCT, CHANGELOG)
```

---

## Metrics

| Metric | Value |
|--------|-------|
| Source connector packages (with `connector.py`) | 17 (+ jira, now implemented — no Candidates left) (+ osv, sentry, pagerduty; + github, fathom, linear, granola, local_directory, google_drive, sarif, slack, notion, mcp_registry, continue_dev, aider) + jira scaffold |
| Total Test Files | 22 (adapter/core + connectors + scripts) |
| Pytest | 202 passed (adapter/core/tests + connectors + scripts/tests) |
| Webhook verify wired | fathom, linear, sentry, pagerduty, jira (Svix/HMAC/multi-sig/sha256= + dedup, fail-closed) |
| CI workflows | 10 gates + 6 reusable `workflow_call` templates (all SHA-pinned) |
| Max File Size | 160 lines (adapter/core/webhook_security.py) |
| Section 4 Violations | 0 (continue_dev 67 lines, aider 73 lines; fns ≤18, nesting ≤2) |

---

## Blueprint Compliance

| Status | Notes |
|--------|-------|
| Delivered | Adapter seam + **12 source connectors** + producer secret screen + L3 webhook signature verification (Svix/Fathom + Linear) + replay dedup + **CI governance/security gate ecosystem** (10 gates + 6 reusable templates) + compliance control mappings — per ADR-0004..0010 |
| Unplanned | 0 |
| Missing | 0 (live REST/GraphQL/poll + secret/keyring resolution + HTTP boundary intentionally deferred per connector `auth.md`; gateway bridge blocked on bicameral-bot #99) |

**Compliance**: aligned with `ARCHITECTURE_PLAN.md` and ADR-0004..0010.

---

## Dependency Manifest

| Scope | Status |
|-------|--------|
| Runtime | stdlib only — no third-party runtime dependencies |
| Dev/CI | ruff, mypy, pytest; CodeQL, Bandit, pip-audit, OpenSSF Scorecard, SBOM, dependency-review, TruffleHog, codespell — all SHA-pinned |

---

## Section 4 Razor Compliance

| Check | Limit | Actual | Status |
|-------|-------|--------|--------|
| Max file size | 250 | 160 (adapter/core/webhook_security.py) | OK |
| Max function size | 40 | ≤40 (verified at audit + observer) | OK |
| Max nesting depth | 3 | ≤3 | OK |

---

## Test Coverage

| Component | Test File | Passing |
|-----------|-----------|---------|
| Pipeline (normalize/validate/screen) | adapter/core/tests/test_pipeline.py | OK (60/60 suite) |
| Sensitive detector | adapter/core/tests/test_sensitive.py | OK |
| GitHub connector | connectors/github/tests/test_github_connector.py | OK |
| Fathom connector | connectors/fathom/tests/test_fathom_connector.py | OK (7) |
| Linear connector | connectors/linear/tests/test_linear_connector.py | OK (7) |
| Granola connector | connectors/granola/tests/test_granola_connector.py | OK (5) |
| Local-directory connector | connectors/local_directory/tests/test_local_directory_connector.py | OK (5) |
| Google Drive connector | connectors/google_drive/tests/test_google_drive_connector.py | OK (10) |
| Webhook security (Svix+Linear verify, dedup) | adapter/core/tests/test_webhook_security.py | OK (16) |
| Fathom webhook verify/dedup | connectors/fathom/tests/test_fathom_webhook.py | OK (7) |
| Linear webhook verify/dedup | connectors/linear/tests/test_linear_webhook.py | OK (10) |
| SARIF connector | connectors/sarif/tests/test_sarif_connector.py | OK |
| Slack connector | connectors/slack/tests/test_slack_connector.py | OK |
| Notion connector | connectors/notion/tests/test_notion_connector.py | OK |
| MCP Registry connector | connectors/mcp_registry/tests/test_mcp_registry_connector.py | OK |
| Continue connector | connectors/continue_dev/tests/test_continue_connector.py | OK |
| Aider connector | connectors/aider/tests/test_aider_connector.py | OK |
| OSV connector | connectors/osv/tests/test_osv_connector.py | OK |
| Sentry connector | connectors/sentry/tests/test_sentry_connector.py | OK |
| PagerDuty connector | connectors/pagerduty/tests/test_pagerduty_connector.py | OK |
| Governance gate (chain + feature-index + `--repo-root`) | scripts/tests/test_governance_gate.py | OK |
| License-header scan | scripts/tests/test_check_license_headers.py | OK |

---

## Health Indicators

| Indicator | Status | Details |
|-----------|--------|---------|
| Ledger Chain | VALID | through Entry #51 (`b5ebb27c`); machine-verified by `scripts/governance_gate.py` |
| Blueprint Sync | SYNCED | ADRs + research briefs + docs/compliance/ + docs/ecosystem/ + all README docs + badges current |
| Section 4 Compliance | PASS | 0 violations |
| Test Status | PASS | 202 passing; ruff + mypy clean (79 files) |
| CI Gates | GREEN (on `main`) | governance-integrity + CodeQL/Bandit/dep-review/Scorecard/SBOM/quality/PR-hygiene + TruffleHog; SHA-pinned; reusable `workflow_call` templates; all PRs merged + CI-verified |

---

## Next Actions

- [x] **connectors-phase1** merged (PR #15).
- [x] **reusable-gate templates** + **AGT-sidecar evaluation** merged (PRs #9/#10).
- [x] **Continue + Aider** connectors merged (PR #16); dependabot CI bumps (#12/#13/#17). All open PRs reconciled onto `main` in order.
- [x] **Security & quality queue** remediated (PR #22, Entry #37): CodeQL URL-host fix + action SHA-pins; 14 alerts closed, 2 admin-gated open (B5).
- [x] **Phase-2 connectors** OSV/Sentry/PagerDuty merged (PR #23, Entry #40).
- [ ] **Connector hardening (next)**: Sentry + PagerDuty live webhook signature verification (HMAC + replay dedup) — extend `adapter/core/webhook_security.py`; PagerDuty needs multi-signature rotation membership-check. Then `verify()`/`normalize_event()` wiring per the Linear/Fathom pattern.
- [ ] **Connector build-out (next)**: Claude Code (P0, passive transcripts/commits), then GitHub Copilot / Cursor / OpenAI-Anthropic Admin (P1 read APIs) — from the value-add shortlist.
- [ ] `mods/` structure is under active build by **Codex** — not edited by this (connector/hardening) track.
- [ ] BACKLOG B3: ecosystem gate rollout to bot/mcp/cloud + AGT sidecar spike (cross-repo). B4: enable Dependency Graph. B5/B6: branch protection + Scorecard Actions-token permission (repo-admin).
- [ ] Add the adapter→gateway conformance test against bicameral-bot `protocol/schemas/v1/` (blocked until bot #99 lands the v1 schema on bot `main`).
- [ ] Track bot #108/#109 (gateway security) and #73 (release posture) as cross-repo dependencies.

---

*State snapshot maintained by Qor-logic. Run `/qor-status` for a live diagnostic.*
