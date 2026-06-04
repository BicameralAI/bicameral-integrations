# System State

## Snapshot Metadata

| Attribute | Value |
|-----------|-------|
| **Last Updated** | 2026-06-04 |
| **Updated By** | Orchestrator (qor-auto-dev-1) |
| **Phase** | SEALED (cycle 6 — connectors-phase1 — substantiated + documented; commit/push/PR authorized) |
| **Iteration** | 6 governed cycles (adapter seam + GitHub; secret screen + CI; 5 connectors; L3 webhook verify; L3 CI governance/security gate ecosystem; **4 Phase-1 parse surfaces + doc pass**) |
| **Session Seal** | `f5b10cb6` (META_LEDGER Entry #26 chain hash) |

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
|   `-- jira/           (scaffold — Candidate, no connector.py yet)
|-- mods/  (dependency_risk, noisy_source_gate, security_mentions — manifests)
|-- docs/  (CONCEPT, ARCHITECTURE_PLAN, META_LEDGER, SHADOW_GENOME,
|          SYSTEM_STATE, GOVERNANCE_INDEX, BACKLOG, FEATURE_INDEX, adr/, research-brief-*)
|-- .github/workflows/  (ci.yml, secret-scan.yml)
`-- (LICENSE, README, CONTRIBUTING, SECURITY, GOVERNANCE, CODE_OF_CONDUCT, CHANGELOG)
```

---

## Metrics

| Metric | Value |
|--------|-------|
| Source connector packages (with `connector.py`) | 10 (github, fathom, linear, granola, local_directory, google_drive, sarif, slack, notion, mcp_registry) + jira scaffold |
| Total Test Files | 15 |
| Pytest | 119 passed (adapter/core/tests + connectors) |
| Max File Size | 160 lines (adapter/core/webhook_security.py) |
| Section 4 Violations | 0 (all 4 new connectors ≤69 lines, fns ≤21, nesting ≤2) |

---

## Blueprint Compliance

| Status | Notes |
|--------|-------|
| Delivered | Adapter seam + 6 source connectors + producer secret screen + **L3 webhook signature verification (Svix/Fathom + Linear) + replay dedup** — per ADR-0004/0005/0006 |
| Unplanned | 0 |
| Missing | 0 (live REST/GraphQL/poll + secret/keyring resolution + HTTP boundary intentionally deferred per connector `auth.md`; gateway bridge blocked on bicameral-bot #99) |

**Compliance**: aligned with `ARCHITECTURE_PLAN.md` and ADR-0004..0007.

---

## Dependency Manifest

| Scope | Status |
|-------|--------|
| Runtime | stdlib only — no third-party runtime dependencies |
| Dev/CI | ruff, mypy, pytest (CI gate); TruffleHog (secret scan) |

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

---

## Health Indicators

| Indicator | Status | Details |
|-----------|--------|---------|
| Ledger Chain | VALID | through Entry #26 (`f5b10cb6`); machine-verified by `scripts/governance_gate.py` |
| Blueprint Sync | SYNCED | ADRs + research briefs + docs/compliance/ + all README docs current |
| Section 4 Compliance | PASS | 0 violations |
| Test Status | PASS | 119 passing; ruff + mypy clean (59 files) |
| CI Gates | GREEN (local) | governance-integrity + CodeQL/Bandit/dep-review/Scorecard/SBOM/quality/PR-hygiene + TruffleHog; SHA-pinned; Review Boundary held (not committed) |

---

## Next Actions

- [ ] **Publish connectors-phase1** (commit authorized): stealth commit (per-connector split) + push + PR for `feat/connectors-phase1` (4 parse surfaces + doc pass).
- [ ] **Evaluate Continue + Aider** as next candidate connectors against the integration criterion (operator request); governed cycle.
- [ ] Remaining live-connector work: REST poll (Fathom/Granola) + Linear GraphQL clients + secret/keyring resolution + watermark/cursor two-phase commit + the live HTTP boundary (webhook signature verification + dedup core DONE).
- [ ] Add the adapter→gateway conformance test against bicameral-bot `protocol/schemas/v1/` (blocked until bot #99 lands the v1 schema on bot `main`).
- [ ] Track bot #108/#109 (gateway security) and #73 (release posture) as cross-repo dependencies.

---

*State snapshot maintained by Qor-logic. Run `/qor-status` for a live diagnostic.*
