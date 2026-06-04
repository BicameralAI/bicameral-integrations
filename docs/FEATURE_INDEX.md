# Bicameral Integrations Feature Index

Single canonical cross-reference of every user-touchable feature in Bicameral Integrations against documentation, source code, and test surface. Updated per the Phase 73 FEATURE_INDEX update obligation in every `/qor-implement` cycle (see `/qor-implement` Step 12.5).

**Generated**: 2026-06-02T03:14:31.4698244-04:00 by `qor-bootstrap`
**Sources**: declared by `/qor-plan` `Feature Inventory Touches` table per cycle.

## Coverage Summary

- Total entries: **36**
- **Verified**: 36
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
| FX-WHSEC-001 | Webhook signature verification + delivery dedup (Svix + hex HMAC + multi-sig) | docs/plan-webhook-verification-dedup-2026-06-04.md | adapter/core/webhook_security.py | adapter/core/tests/test_webhook_security.py | Verified | `verify_standard_webhook` (Svix/Fathom), `verify_hmac_hex` (Linear/Sentry), **`verify_hmac_hex_multi`** (PagerDuty `v1=` rotation membership), `DeliveryDedupCache`; constant-time, fail-closed on all attacker-input paths; L3 |
| FX-WHSEC-002 | Slack `v0` request-signature primitive | docs/plan-webhook-verify-cohort-2026-06-04.md | adapter/core/webhook_security.py | adapter/core/tests/test_webhook_security.py | Verified | `verify_slack_signature` — HMAC-SHA256 over `v0:{ts}:{raw_body}`, `v0=`-prefixed, 300 s replay window (raw timestamp string in basestring); fail-closed on missing/non-numeric ts, stale, missing sig/secret, mismatch; constant-time; L3 |
| FX-GH-002 | GitHub webhook verify + envelope unwrap + dedup | docs/plan-webhook-verify-cohort-2026-06-04.md | connectors/github/connector.py | connectors/github/tests/test_github_webhook.py | Verified | `GitHubConnector.verify`/`normalize_event` (`X-Hub-Signature-256` `sha256=` hex HMAC over raw body, fail-closed; `X-GitHub-Delivery` dedup); unwraps the PR envelope and injects the top-level `number` (test asserts `owner/repo#92` survives); live REST fetch deferred |
| FX-SLACK-002 | Slack webhook verify + dedup wiring | docs/plan-webhook-verify-cohort-2026-06-04.md | connectors/slack/connector.py | connectors/slack/tests/test_slack_webhook.py | Verified | `SlackConnector.verify`/`normalize_event` (`verify_slack_signature` + `X-Slack-Request-Timestamp` 5 m window; `event_id` dedup; signed `url_verification` handshake → `[]`); stale + tamper-with-fresh-timestamp both rejected; live Events-API receipt deferred |
| FX-NOTION-002 | Notion webhook verify + dedup wiring | docs/plan-webhook-verify-cohort-2026-06-04.md | connectors/notion/connector.py | connectors/notion/tests/test_notion_webhook.py | Verified | `NotionConnector.verify`/`normalize_event` (`X-Notion-Signature` `sha256=` hex HMAC over raw body with the verification token; **prefix required** — bare hex rejected; best-effort dedup); live API fetch/OAuth deferred |
| FX-FATHOM-002 | Fathom webhook verify + dedup wiring | docs/plan-webhook-verification-dedup-2026-06-04.md | connectors/fathom/connector.py | connectors/fathom/tests/test_fathom_webhook.py | Verified | `FathomConnector.verify`/`normalize_event` (Svix; injected secret/clock/dedup; self-guarded); live HTTP deferred |
| FX-LINEAR-002 | Linear webhook verify + dedup wiring | docs/plan-webhook-verification-dedup-2026-06-04.md | connectors/linear/connector.py | connectors/linear/tests/test_linear_webhook.py | Verified | `LinearConnector.verify`/`normalize_event` (Linear-Signature HMAC-first + 60s anti-replay; injected secret/clock/dedup; self-guarded); live GraphQL/HTTP deferred |
| FX-SARIF-001 | SARIF 2.1.0 result → Observation parser | docs/plan-connectors-phase1-2026-06-04.md | connectors/sarif/connector.py | connectors/sarif/tests/test_sarif_connector.py | Verified | Catalog P0 (security/compliance-evidence, T0); one Observation per `runs[].results[]`; file import only, live CI-collection deferred |
| FX-SLACK-001 | Slack message event → Observation parser | docs/plan-connectors-phase1-2026-06-04.md | connectors/slack/connector.py | connectors/slack/tests/test_slack_connector.py | Verified | Catalog P0 (communication, T2); `event_callback` envelope or bare message; edit-subtype nested-message unwrap; pinned non-empty excerpt fallback; live Events-API/signature-verify + notify/write (T3+) deferred |
| FX-NOTION-001 | Notion page → Observation parser | docs/plan-connectors-phase1-2026-06-04.md | connectors/notion/connector.py | connectors/notion/tests/test_notion_connector.py | Verified | Catalog P0 (docs, T1); title via `type=="title"` property (id → `notion-page` terminal floor); ACTIVE+WEBHOOK declared, live API/OAuth/block-fetch deferred |
| FX-MCPREG-001 | MCP Registry server entry → Observation parser | docs/plan-connectors-phase1-2026-06-04.md | connectors/mcp_registry/connector.py | connectors/mcp_registry/tests/test_mcp_registry_connector.py | Verified | Catalog P0 (mcp/agent-ecosystem, T1); `server.json` title/description→excerpt, repository.url→url; ACTIVE; read-only scoring/allowlist, live registry-fetch deferred |
| FX-CONTINUE-001 | Continue dev-data event → Observation parser | docs/plan-connectors-dev-tools-2026-06-04.md | connectors/continue_dev/connector.py | connectors/continue_dev/tests/test_continue_connector.py | Verified | Catalog P1 (developer-AI tooling, T0); dev-data JSONL event, prompt/completion→excerpt with `continue {name}` terminal floor; PASSIVE; package `continue_dev` (keyword), source_id `continue`; live file-watch/HTTP-sink/Hub deferred |
| FX-AIDER-001 | Aider attributed git commit → Observation parser | docs/plan-connectors-dev-tools-2026-06-04.md | connectors/aider/connector.py | connectors/aider/tests/test_aider_connector.py | Verified | Catalog P1 (developer-AI tooling, T0); `(aider)` author/committer or Co-authored-by trailer → attributed_by; subject→excerpt with hash→`aider-commit` floor; PASSIVE; live git-log walk + analytics/chat-history deferred |
| FX-OSV-001 | OSV.dev vulnerability record → Observation parser | docs/plan-connectors-phase2-2026-06-04.md | connectors/osv/connector.py | connectors/osv/tests/test_osv_connector.py | Verified | Catalog P0 (security-evidence, T1 no-auth); supply-chain aggregator (GHSA/PyPA/RustSec); summary→excerpt with details→id floor; ACTIVE; SG-I defensive (all-optional schema); live query client deferred |
| FX-SENTRY-001 | Sentry issue webhook → Observation parser | docs/plan-connectors-phase2-2026-06-04.md | connectors/sentry/connector.py | connectors/sentry/tests/test_sentry_connector.py | Verified | Catalog P1 (observability/incident, T1); `data.issue` unwrap; title→excerpt with culprit/shortId/id floor; WEBHOOK; live Events-API/`Sentry-Hook-Signature` verify deferred |
| FX-PAGERDUTY-001 | PagerDuty v3 incident webhook → Observation parser | docs/plan-connectors-phase2-2026-06-04.md | connectors/pagerduty/connector.py | connectors/pagerduty/tests/test_pagerduty_connector.py | Verified | Catalog P1 (observability/incident, T1); nested `event.data` unwrap; title→excerpt with summary/id floor; WEBHOOK |
| FX-SENTRY-002 | Sentry webhook verify + dedup wiring | docs/plan-webhook-hardening-2026-06-04.md | connectors/sentry/connector.py | connectors/sentry/tests/test_sentry_connector.py | Verified | `SentryConnector.verify`/`normalize_event` (hex HMAC over RAW body; injected secret/dedup; self-guarded; best-effort dedup, no replay window per Sentry); live HTTP receipt deferred |
| FX-PAGERDUTY-002 | PagerDuty webhook verify + dedup wiring | docs/plan-webhook-hardening-2026-06-04.md | connectors/pagerduty/connector.py | connectors/pagerduty/tests/test_pagerduty_connector.py | Verified | `PagerDutyConnector.verify`/`normalize_event` (multi-signature `v1=` membership via `verify_hmac_hex_multi`; injected secret/dedup; self-guarded); live HTTP receipt deferred; first-party scheme spot-check pending (BACKLOG) |
| FX-CLAUDECODE-001 | Claude Code transcript line → Observation parser | docs/plan-claude-code-2026-06-04.md | connectors/claude_code/connector.py | connectors/claude_code/tests/test_claude_code_connector.py | Verified | Catalog P0 (developer-AI tooling, T0); `~/.claude/**/*.jsonl` heterogeneous event log → `parse_session_line` filters to user/assistant/summary (meta/unknown→None); `[claude-code:{kind}] {uuid}` terminal floor; depth-capped + type-defensive (SG-I); PASSIVE; live file-watch/history/git-attribution deferred |
| FX-JIRA-001 | Jira Cloud issue webhook → Observation parser + verify | docs/plan-jira-2026-06-04.md | connectors/jira/connector.py | connectors/jira/tests/test_jira_connector.py | Verified | Catalog P0 (project-management, T1); `parse_issue` (summary→excerpt, never ADF description, `jira-issue` floor); `JiraConnector.verify`/`normalize_event` (`X-Hub-Signature` `sha256=` hex HMAC over raw body, fail-closed; best-effort dedup on `X-Atlassian-Webhook-Identifier`); WEBHOOK+ACTIVE; live HTTP/REST + Connect-JWT deferred |

---

## Section: Runtime Boundary

| ID | Feature | Doc | Code | Test | Status | Notes |
|---|---|---|---|---|---|---|
| FX-RUNTIME-001 | Operator-runtime boundary layer (sinks + delivery + secret resolver) | docs/adr/0012-connector-readiness-ladder-and-live-ingest-runtime.md, docs/plan-go-live-runtime-2026-06-04.md | runtime/sinks.py, runtime/delivery.py, runtime/secrets.py | runtime/tests/test_runtime.py | Verified | `EmissionSink`/`SecretResolver` Protocols + `CollectingSink` + `GatewaySink` (#109-gated stub raising `GatewayEmissionGated`) + `deliver_webhook`/`deliver_poll`; drives connector ingest→verify→normalize→emit without the repo being a server (ADR-0012). **Beta cohort proven through the harness**: signed-webhook→1 + bad-sig→0 for **linear** (HMAC+replay), **fathom** (Svix), **sentry** (hex HMAC), **pagerduty** (multi-sig membership — valid sig placed 2nd), **github** (sha256= + envelope unwrap), **slack** (v0 basestring), **notion** (sha256= prefix-pinned); deliver_poll(OSV)→2; GatewaySink raises |

---

## Section: CI & Governance Gates

| ID | Feature | Doc | Code | Test | Status | Notes |
|---|---|---|---|---|---|---|
| FX-CI-GOV-001 | Governance-integrity gate (ledger hash-chain + FEATURE_INDEX) | docs/plan-ci-governance-gates-2026-06-04.md | scripts/governance_gate.py | scripts/tests/test_governance_gate.py | Verified | stdlib; genesis-anchor rule (SG-2026-06-04-D); blocking via governance-gate.yml; verifies committed ledger + test paths |
| FX-CI-SEC-001 | Security + supply-chain gates | docs/plan-ci-governance-gates-2026-06-04.md | .github/workflows/codeql.yml | (D4.d waiver) | Verified | CodeQL/Bandit/dependency-review/Scorecard/SBOM/pip-audit/Dependabot, SHA-pinned; config validated by workflow-lint + tools executing |
| FX-CI-QUAL-001 | Quality/consistency gates | docs/plan-ci-governance-gates-2026-06-04.md | scripts/check_license_headers.py | scripts/tests/test_check_license_headers.py | Verified | workflow-YAML lint + codespell + SPDX-header scan (advisory) + conventional PR title |
| FX-CI-DOC-001 | Compliance framework mappings | docs/plan-ci-governance-gates-2026-06-04.md | docs/compliance/README.md | (D4.d waiver) | Verified | OWASP/NIST/EU-AI-Act/SOC2/GDPR+HIPAA control mappings; backbone is FX-CI-GOV-001; "alignment, not certification" |
| FX-CI-GOV-002 | Governance gate `--repo-root` (cross-repo verify) | docs/plan-reusable-gates-2026-06-04.md | scripts/governance_gate.py | scripts/tests/test_governance_gate.py | Verified | `main(--repo-root/--ledger/--feature-index)`; default unchanged; enables reusable cross-repo verification (SG-2026-06-04-E) |
| FX-CI-REUSE-001 | Reusable-workflow gate template | docs/plan-reusable-gates-2026-06-04.md | .github/workflows/_reusable-governance-gate.yml | (D4.d waiver) | Verified | portable gates as `workflow_call`; this repo dogfoods via thin callers; validated by workflow-lint + governance gate exit 0 |
| FX-CI-DOC-002 | Ecosystem gate-adoption guide | docs/plan-reusable-gates-2026-06-04.md | docs/ecosystem/consuming-gates.md | (D4.d waiver) | Verified | how bot/mcp/cloud consume the reusables + SHA-pin + --repo-root contract; backed by FX-CI-REUSE-001 |

---

## Gaps Surfaced

<!-- Reality without Promise / Promise without Reality entries land here. -->
