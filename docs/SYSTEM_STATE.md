# System State

## Snapshot Metadata

| Attribute | Value |
|-----------|-------|
| **Last Updated** | 2026-06-03 |
| **Updated By** | Orchestrator (qor-auto-dev-1) |
| **Phase** | IMPLEMENTING (cycle 4 substantiated; Review Boundary held — local only) |
| **Iteration** | 4 governed cycles (adapter seam + GitHub; secret screen + CI; 5 connectors; **L3 webhook verify + dedup**) |
| **Session Seal** | `8a914301` (META_LEDGER Entry #17 chain hash) |

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
|   `-- jira/           (scaffold — no MCP impl; research-only)
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
| Source connector packages (with `connector.py`) | 6 (github, fathom, linear, granola, local_directory, google_drive) |
| Total Test Files | 11 |
| Pytest | 93 passed (adapter/core/tests + connectors) |
| Max File Size | 160 lines (adapter/core/webhook_security.py) |
| Section 4 Violations | 0 (google_drive `_walk_table` refactored to ≤3 nesting this cycle) |

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

---

## Health Indicators

| Indicator | Status | Details |
|-----------|--------|---------|
| Ledger Chain | VALID | through Entry #17 (`8a914301`) |
| Blueprint Sync | SYNCED | ADRs + 4 research briefs current (incl. webhook-verification) |
| Section 4 Compliance | PASS | 0 violations |
| Test Status | PASS | 93 passing; ruff + mypy clean (43 files) |
| CI Gates | GREEN (local) | ci.yml covers `adapter connectors`; Review Boundary held (not yet committed) |

---

## Next Actions

- [ ] **User review of cycles 3+4** (held at Review Boundary): both stack on `feat/source-connectors-fathom-linear` (5 connectors + L3 webhook verify/dedup). Review staged tree + governance updates, then commit/PR when ready.
- [ ] Remaining live-connector work: REST poll (Fathom/Granola) + Linear GraphQL clients + secret/keyring resolution + watermark/cursor two-phase commit + the live HTTP boundary (webhook signature verification + dedup core now DONE this cycle).
- [ ] Add the adapter→gateway conformance test against bicameral-bot `protocol/schemas/v1/` (blocked until bot #99 lands the v1 schema on bot `main`).
- [ ] Track bot #108/#109 (gateway security) and #73 (release posture) as cross-repo dependencies.

---

*State snapshot maintained by Qor-logic. Run `/qor-status` for a live diagnostic.*
