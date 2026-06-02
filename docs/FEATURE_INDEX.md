# Bicameral Integrations Feature Index

Single canonical cross-reference of every user-touchable feature in Bicameral Integrations against documentation, source code, and test surface. Updated per the Phase 73 FEATURE_INDEX update obligation in every `/qor-implement` cycle (see `/qor-implement` Step 12.5).

**Generated**: 2026-06-02T03:14:31.4698244-04:00 by `qor-bootstrap`
**Sources**: declared by `/qor-plan` `Feature Inventory Touches` table per cycle.

## Coverage Summary

- Total entries: **2**
- **Verified**: 2
- **Unverified**: 0
- **N/A (operator-justified)**: 0

---

## Section: Integrations

| ID | Feature | Doc | Code | Test | Status | Notes |
|---|---|---|---|---|---|---|
| FX-ADP-001 | Universal adapter normalization seam (`normalize` + `validate_emissions`) | docs/plan-adapter-core-github-connector-2026-06-02.md | adapter/core/pipeline.py, adapter/core/observations.py | adapter/core/tests/test_pipeline.py | Verified | Observation→AdapterEmission seam; enforces ADR-0005 contract rules |
| FX-GH-001 | GitHub PR → Observation parser | docs/plan-adapter-core-github-connector-2026-06-02.md | connectors/github/connector.py | connectors/github/tests/test_github_connector.py | Verified | Fixture-based; live fetch_active/webhook deferred (no live API this cycle) |

---

## Gaps Surfaced

<!-- Reality without Promise / Promise without Reality entries land here. -->
