# Bicameral Integrations Feature Index

Single canonical cross-reference of every user-touchable feature in Bicameral Integrations against documentation, source code, and test surface. Updated per the Phase 73 FEATURE_INDEX update obligation in every `/qor-implement` cycle (see `/qor-implement` Step 12.5).

**Generated**: 2026-06-02T03:14:31.4698244-04:00 by `qor-bootstrap`
**Sources**: declared by `/qor-plan` `Feature Inventory Touches` table per cycle.

## Coverage Summary

- Total entries: **19**
- **Verified**: 19
- **Unverified**: 0
- **N/A (operator-justified)**: 0

---

## Section: Integrations

| ID | Feature | Doc | Code | Test | Status | Notes |
|---|---|---|---|---|---|---|
| FX-ADP-001 | Universal adapter normalization seam (`normalize` + `validate_emissions`) | docs/plan-adapter-core-github-connector-2026-06-02.md | adapter/core/pipeline.py, adapter/core/observations.py | adapter/core/tests/test_pipeline.py | Verified | Observation→AdapterEmission seam; enforces ADR-0005 contract rules |
| FX-GH-001 | GitHub PR → Observation parser | docs/plan-adapter-core-github-connector-2026-06-02.md | connectors/github/connector.py | connectors/github/tests/test_github_connector.py | Verified | Fixture-based; live fetch_active/webhook deferred (no live API this cycle) |
| FX-SEC-001 | Producer sensitive-data screen (secret/PHI/PAN) | docs/plan-security-governance-alignment-2026-06-03.md | adapter/core/sensitive.py, adapter/core/pipeline.py | adapter/core/tests/test_sensitive.py | Verified | Port of mcp sensitive_patterns; HARD-gate in validate_emissions; secret excerpts redacted (no leak) |
| FX-FATHOM-001 | Fathom meeting → Observation parser | docs/plan-source-connectors-fathom-linear-ports-2026-06-03.md | connectors/fathom/connector.py | connectors/fathom/tests/test_fathom_connector.py | Verified | Net-new (developers.fathom.ai); transcript→excerpt (summary/title fallback); PASSIVE+WEBHOOK declared, live REST/Svix-verify deferred |
| FX-LINEAR-001 | Linear webhook event → Observation parser | docs/plan-source-connectors-fathom-linear-ports-2026-06-03.md | connectors/linear/connector.py | connectors/linear/tests/test_linear_connector.py | Verified | Net-new (linear.app/developers); Issue envelope, action/type→metadata; WEBHOOK+ACTIVE declared, live GraphQL/Linear-Signature-verify deferred |
| FX-GRANOLA-001 | Granola transcript → Observation parser | docs/plan-source-connectors-fathom-linear-ports-2026-06-03.md | connectors/granola/connector.py | connectors/granola/tests/test_granola_connector.py | Verified | Port of mcp events/sources/granola.py; PASSIVE; live poll/watermark deferred |
| FX-LOCALDIR-001 | Local-directory file → Observation parser | docs/plan-source-connectors-fathom-linear-ports-2026-06-03.md | connectors/local_directory/connector.py | connectors/local_directory/tests/test_local_directory_connector.py | Verified | Port of mcp events/sources/local_directory.py; PASSIVE; sha256 path token ref; live scan/watermark deferred |
| FX-GDRIVE-001 | Google Docs document → Observation parser | docs/plan-source-connectors-fathom-linear-ports-2026-06-03.md | connectors/google_drive/connector.py | connectors/google_drive/tests/test_google_drive_connector.py | Verified | Port of mcp google_drive adapter; structured-body flatten; ACTIVE; _walk_table refactored ≤3 nesting; live Docs API/OAuth deferred |
| FX-WHSEC-001 | Webhook signature verification + delivery dedup (Svix + hex HMAC) | docs/plan-webhook-verification-dedup-2026-06-04.md | adapter/core/webhook_security.py | adapter/core/tests/test_webhook_security.py | Verified | `verify_standard_webhook` (Svix/Fathom), `verify_hmac_hex` (Linear), `DeliveryDedupCache`; constant-time, fail-closed on all attacker-input paths; L3 |
| FX-FATHOM-002 | Fathom webhook verify + dedup wiring | docs/plan-webhook-verification-dedup-2026-06-04.md | connectors/fathom/connector.py | connectors/fathom/tests/test_fathom_webhook.py | Verified | `FathomConnector.verify`/`normalize_event` (Svix; injected secret/clock/dedup; self-guarded); live HTTP deferred |
| FX-LINEAR-002 | Linear webhook verify + dedup wiring | docs/plan-webhook-verification-dedup-2026-06-04.md | connectors/linear/connector.py | connectors/linear/tests/test_linear_webhook.py | Verified | `LinearConnector.verify`/`normalize_event` (Linear-Signature HMAC-first + 60s anti-replay; injected secret/clock/dedup; self-guarded); live GraphQL/HTTP deferred |
| FX-SARIF-001 | SARIF 2.1.0 result → Observation parser | docs/plan-connectors-phase1-2026-06-04.md | connectors/sarif/connector.py | connectors/sarif/tests/test_sarif_connector.py | Verified | Catalog P0 (security/compliance-evidence, T0); one Observation per `runs[].results[]`; file import only, live CI-collection deferred |
| FX-SLACK-001 | Slack message event → Observation parser | docs/plan-connectors-phase1-2026-06-04.md | connectors/slack/connector.py | connectors/slack/tests/test_slack_connector.py | Verified | Catalog P0 (communication, T2); `event_callback` envelope or bare message; edit-subtype nested-message unwrap; pinned non-empty excerpt fallback; live Events-API/signature-verify + notify/write (T3+) deferred |
| FX-NOTION-001 | Notion page → Observation parser | docs/plan-connectors-phase1-2026-06-04.md | connectors/notion/connector.py | connectors/notion/tests/test_notion_connector.py | Verified | Catalog P0 (docs, T1); title via `type=="title"` property (id → `notion-page` terminal floor); ACTIVE+WEBHOOK declared, live API/OAuth/block-fetch deferred |
| FX-MCPREG-001 | MCP Registry server entry → Observation parser | docs/plan-connectors-phase1-2026-06-04.md | connectors/mcp_registry/connector.py | connectors/mcp_registry/tests/test_mcp_registry_connector.py | Verified | Catalog P0 (mcp/agent-ecosystem, T1); `server.json` title/description→excerpt, repository.url→url; ACTIVE; read-only scoring/allowlist, live registry-fetch deferred |

---

## Section: CI & Governance Gates

| ID | Feature | Doc | Code | Test | Status | Notes |
|---|---|---|---|---|---|---|
| FX-CI-GOV-001 | Governance-integrity gate (ledger hash-chain + FEATURE_INDEX) | docs/plan-ci-governance-gates-2026-06-04.md | scripts/governance_gate.py | scripts/tests/test_governance_gate.py | Verified | stdlib; genesis-anchor rule (SG-2026-06-04-D); blocking via governance-gate.yml; verifies committed ledger + test paths |
| FX-CI-SEC-001 | Security + supply-chain gates | docs/plan-ci-governance-gates-2026-06-04.md | .github/workflows/codeql.yml | (D4.d waiver) | Verified | CodeQL/Bandit/dependency-review/Scorecard/SBOM/pip-audit/Dependabot, SHA-pinned; config validated by workflow-lint + tools executing |
| FX-CI-QUAL-001 | Quality/consistency gates | docs/plan-ci-governance-gates-2026-06-04.md | scripts/check_license_headers.py | scripts/tests/test_check_license_headers.py | Verified | workflow-YAML lint + codespell + SPDX-header scan (advisory) + conventional PR title |
| FX-CI-DOC-001 | Compliance framework mappings | docs/plan-ci-governance-gates-2026-06-04.md | docs/compliance/README.md | (D4.d waiver) | Verified | OWASP/NIST/EU-AI-Act/SOC2/GDPR+HIPAA control mappings; backbone is FX-CI-GOV-001; "alignment, not certification" |

---

## Gaps Surfaced

<!-- Reality without Promise / Promise without Reality entries land here. -->
