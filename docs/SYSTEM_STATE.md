# System State

## Snapshot Metadata

| Attribute | Value |
|-----------|-------|
| **Last Updated** | [ISO 8601 timestamp] |
| **Updated By** | [Governor \| Judge \| Specialist] |
| **Phase** | [BOOTSTRAP \| IMPLEMENTING \| SUBSTANTIATED] |
| **Iteration** | [N] |
| **Session Seal** | [hash prefix or PENDING] |

---

## File Tree (Current Reality)

<!--
This is the ACTUAL state of the project, not the planned state.
Updated by /qor-substantiate or /qor-refactor.
-->

```
project/
|-- .agent/
|   `-- staging/
|       `-- AUDIT_REPORT.md
|-- docs/
|   |-- CONCEPT.md
|   |-- ARCHITECTURE_PLAN.md
|   |-- META_LEDGER.md
|   |-- SYSTEM_STATE.md (this file)
|   `-- SHADOW_GENOME.md
|-- src/
|   `-- [actual source tree]
|-- tests/
|   `-- [actual test tree]
`-- [other project files]
```

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Source Files | [count] |
| Total Test Files | [count] |
| Total Lines of Code | [count] |
| Average File Size | [lines] |
| Max File Size | [lines] (file: [name]) |
| Max Function Size | [lines] (file: [name]) |
| Section 4 Violations | [count] |

---

## Blueprint Compliance

<!--
Compare ARCHITECTURE_PLAN.md (Promise) vs actual files (Reality).
-->

| Status | Planned | Actual | Notes |
|--------|---------|--------|-------|
| OK Delivered | [count] | [count] | Files matching blueprint |
| WARN Unplanned | 0 | [count] | Files not in blueprint |
| FAIL Missing | [count] | 0 | Planned but not created |

**Compliance Rate**: [percentage]%

---

## Dependency Manifest

<!--
Current dependencies vs what was approved in blueprint.
-->

| Package | Approved | Installed | Status |
|---------|----------|-----------|--------|
| [name] | OK | OK | OK |
| [name] | FAIL | OK | UNPLANNED |
| [name] | OK | FAIL | MISSING |

---

## Section 4 Razor Compliance

### File-Level (Macro KISS)

| File | Lines | Status |
|------|-------|--------|
| [path] | [N]/250 | OK/FAIL |

### Function-Level (Micro KISS)

| File | Longest Function | Deepest Nesting | Status |
|------|-----------------|-----------------|--------|
| [path] | [N]/40 lines | [N]/3 levels | OK/FAIL |

---

## Test Coverage

| Component | Test File | Exists | Passing |
|-----------|-----------|--------|---------|
| [name] | [path] | OK/FAIL | OK/FAIL/- |

---

## Recent Changes

<!--
List of files modified in current iteration.
-->

| File | Change Type | Lines Changed |
|------|-------------|---------------|
| [path] | [Created \| Modified \| Deleted] | [+N, -M] |

---

## Health Indicators

| Indicator | Status | Details |
|-----------|--------|---------|
| Merkle Chain | [VALID \| BROKEN] | Last validated: [date] |
| Blueprint Sync | [SYNCED \| DRIFT] | [details] |
| Section 4 Compliance | [PASS \| VIOLATIONS] | [count] violations |
| Test Status | [PASS \| FAIL \| UNKNOWN] | [details] |

---

## Next Actions

Based on current state:

- [ ] [Recommended action 1]
- [ ] [Recommended action 2]

---

*State snapshot updated by Qor-logic A.E.G.I.S.*
*Run `/qor-status` for live diagnostic.*
