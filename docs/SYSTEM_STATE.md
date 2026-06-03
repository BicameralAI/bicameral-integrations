# System State

## Snapshot Metadata

| Attribute | Value |
|-----------|-------|
| **Last Updated** | 2026-06-03 |
| **Updated By** | Orchestrator (qor-auto-dev-1) |
| **Phase** | IMPLEMENTING (cycles 1–2 substantiated & merged to `main`) |
| **Iteration** | 2 governed cycles (adapter seam + GitHub connector; secret screen + CI alignment) |
| **Session Seal** | `cad649f6` (META_LEDGER Entry #9 chain hash) |

---

## File Tree (Current Reality)

```
bicameral-integrations/
|-- adapter/
|   `-- core/  (emissions, observations, contracts, capabilities, pipeline,
|              sensitive, filters, fixtures, __init__ + tests/)
|-- connectors/
|   |-- github/  (connector.py, fixtures/pr_merged.json, tests/)
|   |-- google_drive/  (scaffold)
|   `-- jira/  (scaffold)
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
| Total Source Files (.py, excl. tests) | 16 |
| Total Test Files | 3 |
| Total Lines of Code (source) | 564 |
| Max File Size | 132 lines (adapter/core/sensitive.py) |
| Section 4 Violations | 0 |

---

## Blueprint Compliance

| Status | Notes |
|--------|-------|
| Delivered | Universal adapter normalization seam + GitHub connector + producer secret screen — all per ADR-0004/0005/0006 |
| Unplanned | 0 |
| Missing | 0 (gateway bridge intentionally deferred — blocked on bicameral-bot#92/#109) |

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
| Max file size | 250 | 132 (sensitive.py) | OK |
| Max function size | 40 | ≤40 (verified at audit) | OK |
| Max nesting depth | 3 | ≤3 | OK |

---

## Test Coverage

| Component | Test File | Passing |
|-----------|-----------|---------|
| Pipeline (normalize/validate/screen) | adapter/core/tests/test_pipeline.py | 26/26 suite OK |
| Sensitive detector | adapter/core/tests/test_sensitive.py | OK |
| GitHub connector | connectors/github/tests/test_github_connector.py | OK |

---

## Health Indicators

| Indicator | Status | Details |
|-----------|--------|---------|
| Ledger Chain | VALID | through Entry #9 (`cad649f6`) |
| Blueprint Sync | SYNCED | ADRs + research briefs current |
| Section 4 Compliance | PASS | 0 violations |
| Test Status | PASS | 26 passing; ruff + mypy clean |
| CI Gates | GREEN | ci.yml + TruffleHog passing on `main` |

---

## Next Actions

- [ ] Add the adapter→gateway conformance test against bicameral-bot `protocol/schemas/v1/` (blocked until bot #99 lands the v1 schema on bot `main`).
- [ ] Track bot #108/#109 (gateway security) and #73 (release posture) as cross-repo dependencies.

---

*State snapshot maintained by Qor-logic. Run `/qor-status` for a live diagnostic.*
