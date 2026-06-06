# System State

## Snapshot Metadata

| Attribute | Value |
|-----------|-------|
| **Last Updated** | 2026-06-05 |
| **Updated By** | Orchestrator (qor-auto-dev-1) |
| **Phase** | `main` + **security red-team COMPLETE (Cycles A/B/C, GH #50-#61 all closed)** — Cycle C: id-less webhook replays deduped by body hash for the 4 windowless providers (#60; bounded-cache eviction/TTL residual documented); emission contract rejects zero-width-only excerpt + bounds `source_id` (#61). Cores were sound; the 12 edge findings (guarantee-violations A, DoS/robustness B, replay/nits C) are all fixed. 26 Beta connectors; parse surfaces hardened — the before-Live DoS gate is cleared |
| **Iteration** | 30 governed cycles (… redaction retrofit; references.md parity; security red-team **Cycle A** (#52/#53/#54), **Cycle B** (#50/#51/#55-#59 DoS), **Cycle C** (#60 replay / #61 nits) — all 12 red-team issues closed) |
| **Session Seal** | `<pending Entry #90>` (prior tip `563f9938` — Entry #88) |

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
|   |-- claude_code/    (transcript line -> Observation; PASSIVE; T0)
|   |-- jira/           (issue webhook -> Observation + verify; WEBHOOK+ACTIVE; T1)
|   `-- zendesk/        (ticket webhook -> Observation + verify; WEBHOOK+ACTIVE; T1)
|-- runtime/  (operator-runtime boundary, ADR-0012: sinks, secrets, delivery,
|              poll_client + poll_auth + poll_specs + tests — EmissionSink/SecretResolver
|              Protocols, deliver_webhook/deliver_poll, GatewaySink real Live emission seam
|              (POST /api/v1/ingest), poll_client live-poll fetch half
|              (HttpTransport-injected; object|array pages; PageToken + OffsetPager pagination;
|              GET + POST body), poll_auth (ApiKeyHeader/Bearer/Basic), poll_specs per-connector
|              wiring (anthropic/openai/copilot/devin/granola/cursor/servicenow);
|              library-only, stdlib urllib)
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
| Source connector packages (with `connector.py`) | 26 (+ openai_admin, anthropic_admin; devin, servicenow, copilot, cursor, gitlab, confluence, zendesk, github, fathom, linear, granola, local_directory, google_drive, sarif, slack, notion, mcp_registry, continue_dev, aider, claude_code, osv, sentry, pagerduty, jira) |
| Readiness ladder (ADR-0012) | **Beta: 26 (ALL connectors)** — every connector earned Beta via a real runtime-harness proof · **Prototype: 0** · **Live: 0 connectors** (the **Live seam is implemented + operator-actionable** now bot #109 landed — Live is earned by an operator wiring `GatewaySink` against a real gateway, not by the repo) |
| PII handling | FX-SEC-001 hard screen (secret/PHI/PAN reject) + **`adapter/core/redaction.py::redact` redact-and-pass** (scrubs secret/PHI/PAN value-consuming + email/phone; invariant `detect_sensitive(redact(x))==[]`; composes with, never replaces, the screen). Used by devin/servicenow/**zendesk** (ticket body now redact-and-pass); openai_admin/copilot drop-at-parse (openai_admin drops actor email/IP). **Cursor**: email/name dropped, opaque `userId` surfaced for per-developer attribution (SG-2026-06-05-D; residual re-id risk = operator holds id→identity mapping, accepted) |
| Runtime boundary | `runtime/` library layer (sinks + secrets + delivery + **gateway_mapping**); **GatewaySink = real Live emission** (v1 IngestRequest → `POST /api/v1/ingest`, default-safe + fail-closed + secret-safe) |
| Total Test Files | 40 (adapter/core + connectors + runtime + scripts) |
| Pytest | 361 passed (adapter/core/tests + connectors + runtime + scripts/tests) |
| Webhook verify wired | fathom, linear, sentry, pagerduty, jira, github, slack, notion, zendesk, gitlab (Svix/HMAC/multi-sig/sha256=/v0/Base64/plaintext-token + dedup, fail-closed) |
| CI workflows | 10 gates + 6 reusable `workflow_call` templates (all SHA-pinned) |
| Max File Size | 160 lines (adapter/core/webhook_security.py) |
| Section 4 Violations | 0 (continue_dev 67 lines, aider 73 lines; fns ≤18, nesting ≤2) |

---

## Blueprint Compliance

| Status | Notes |
|--------|-------|
| Delivered | Adapter seam + **17 source connectors** + producer secret screen + L3 webhook signature verification (Svix/Fathom, Linear, Sentry, PagerDuty hex/multi-sig, Jira `sha256=`) + replay dedup + **CI governance/security gate ecosystem** (10 gates + 6 reusable templates) + compliance control mappings — per ADR-0004..0010 |
| Unplanned | 0 |
| Missing | 0. **Gateway emission is now implemented** — `GatewaySink` maps to the pinned v1 `IngestRequest` and POSTs to `/api/v1/ingest`; bot **#109 CLOSED/COMPLETED** (PR #131 ingest guards: body-size/rate/sensitive-data). What remains operator-owned (per connector `auth.md`, not "missing"): the live HTTP receiver/poller + secret/keyring resolution + configuring `GatewaySink(endpoint=…, token=…)` against a real gateway — i.e. the operator deployment that earns a connector **Live**. |

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
| Claude Code connector | connectors/claude_code/tests/test_claude_code_connector.py | OK |
| Jira connector | connectors/jira/tests/test_jira_connector.py | OK |
| GitLab connector | connectors/gitlab/tests/test_gitlab_connector.py | OK |
| Confluence connector | connectors/confluence/tests/test_confluence_connector.py | OK |
| Copilot connector | connectors/copilot/tests/test_copilot_connector.py | OK |
| Cursor connector (PII-drop proven) | connectors/cursor/tests/test_cursor_connector.py | OK |
| Devin connector (session body redacted) | connectors/devin/tests/test_devin_connector.py | OK |
| ServiceNow connector (redact-and-pass; caller dropped) | connectors/servicenow/tests/test_servicenow_connector.py | OK |
| Redaction-and-pass primitive (invariant `detect(redact(x))==[]`) | adapter/core/tests/test_redaction.py | OK |
| OpenAI Admin connector (actor identity dropped) | connectors/openai_admin/tests/test_openai_admin_connector.py | OK |
| Anthropic Admin connector (aggregate, PII-free) | connectors/anthropic_admin/tests/test_anthropic_admin_connector.py | OK |
| Runtime boundary (all 26 connectors end-to-end: deliver_webhook + deliver_poll; full-path → GatewaySink) | runtime/tests/test_runtime.py | OK (43) |
| Live emission seam (emission→v1 mapping; GatewaySink POST: 201-only, gated, token-safe, real round-trip) | runtime/tests/test_gateway_mapping.py | OK (12) |
| Live-poll client (fetch half: request+auth+pagination over recorded transport; fail-closed; token-safe; 7 connectors: anthropic + Bearer openai/copilot/devin/granola + Basic cursor(POST)/servicenow(offset)) | runtime/tests/test_poll_client.py | OK (26) |
| Zendesk connector + webhook verify/dedup (Base64 HMAC) | connectors/zendesk/tests/ | OK (11) |
| GitHub webhook verify/dedup (envelope unwrap) | connectors/github/tests/test_github_webhook.py | OK (6) |
| Slack webhook verify/dedup (v0 + replay) | connectors/slack/tests/test_slack_webhook.py | OK (7) |
| Notion webhook verify/dedup (sha256= pinned) | connectors/notion/tests/test_notion_webhook.py | OK (6) |
| Governance gate (chain + feature-index + `--repo-root`) | scripts/tests/test_governance_gate.py | OK |
| License-header scan | scripts/tests/test_check_license_headers.py | OK |

---

## Health Indicators

| Indicator | Status | Details |
|-----------|--------|---------|
| Ledger Chain | VALID | through Entry #90 (`5b9c4d17`); machine-verified by `scripts/governance_gate.py` |
| Blueprint Sync | SYNCED | ADRs (incl. 0012) + research briefs + docs/compliance/ + docs/ecosystem/ + all README docs (main README connector+mod index refreshed) + badges current |
| Section 4 Compliance | PASS | 0 violations |
| Test Status | PASS | 361 passing; ruff + mypy clean |
| CI Gates | **6/6 green** (verified) | CI + CodeQL + Governance Gate + Quality + Security Scan + **OpenSSF Scorecard** all `success` on `main` (Scorecard green confirmed by run `26980983204` after the B6 v2 permission fix — SG-2026-06-04-O). Security-tab posture hardened (B13): Token-Permissions #21-24 fixed (write scopes moved to the calling-job level, top-level read-only); stale CodeQL #17 + accepted Pinned-Dependencies #18-20 dismissed via API with rationale. Only #13/#1 (Code-Review, Branch-Protection) remain — they need branch protection (B5, repo-admin). SBOM gate carries a latent OIDC twin (B12), release-only. SHA-pinned; reusable `workflow_call` templates. |

---

## Next Actions

- [x] **connectors-phase1** merged (PR #15).
- [x] **reusable-gate templates** + **AGT-sidecar evaluation** merged (PRs #9/#10).
- [x] **Continue + Aider** connectors merged (PR #16); dependabot CI bumps (#12/#13/#17). All open PRs reconciled onto `main` in order.
- [x] **Security & quality queue** remediated (PR #22, Entry #37): CodeQL URL-host fix + action SHA-pins; 14 alerts closed, 2 admin-gated open (B5).
- [x] **Phase-2 connectors** OSV/Sentry/PagerDuty merged (PR #23, Entry #40).
- [x] **Phase-2 webhook hardening** Sentry + PagerDuty verify/dedup wired (FX-SENTRY-002/FX-PAGERDUTY-002); **Claude Code** (FX-CLAUDECODE-001) + **Jira** (FX-JIRA-001) connectors built — 17 connectors, no Candidates left.
- [x] **Go-live runtime boundary** (ADR-0012) shipped: `runtime/` library layer (sinks/secrets/delivery, GatewaySink #109-gated stub) + **Linear → Beta** end-to-end (Entry #55, FX-RUNTIME-001).
- [x] **Beta cohort promoted**: Fathom (Svix) + Sentry (HMAC) + PagerDuty (multi-sig membership) proven end-to-end via the `runtime/` harness — **4 Beta connectors** (incl. Linear), zero cross-repo dep.
- [x] **GitHub/Slack/Notion verify-wired → Beta** (`verify_slack_signature` primitive + per-connector `verify()`/`normalize_event()`; harness-proven). **7 Beta connectors.**
- [x] **Scorecard Token-Permissions hardening (B13)** — done (Entry #63); Security tab down to #13/#1 (branch protection, B5, admin).
- [x] **CS/support/sales evaluation** (Zendesk/ServiceNow/ChurnZero/Gainsight) — done (Entry #64): all evidence adapters; **Zendesk P1** (webhook-first, gated on PII redaction), ServiceNow P2, ChurnZero/Gainsight P3.
- [x] **Zendesk connector → Beta** (Entry #66): P1 support evidence; `parse_ticket` + `verify_zendesk_signature` (Base64 HMAC).
- [x] **Beta graduation (Entry #68): every connector earned Beta** — 18 Beta / 0 Prototype; each via a real runtime-harness proof (deliver_webhook / deliver_poll), not a doc flip. Posted the integrations-side dependency on bot #109 (Live gate).
- [ ] **Next (operator decision)**: the PII **redaction-and-pass model** (unblocks live Zendesk + CS set); ServiceNow (P2); GitHub Copilot/Cursor/Admin (P1); **Live-stage wiring when bot #109 lands** (GatewaySink → real emission). Admin: branch protection (B5).
- [ ] **Connector build-out (next)**: GitHub Copilot / Cursor / OpenAI-Anthropic Admin (P1 read APIs) — from the value-add shortlist; B9 Devin (P1).
- [ ] `mods/` structure is under active build by **Codex** — not edited by this (connector/hardening) track.
- [ ] BACKLOG B3: ecosystem gate rollout to bot/mcp/cloud + AGT sidecar spike (cross-repo). B4: enable Dependency Graph. B5/B6: branch protection + Scorecard Actions-token permission (repo-admin).
- [ ] adapter→gateway emission: map `AdapterEmission` to the **published** v1 ingest schema (bot PR #95, `protocol/schemas/v1/`) + a conformance test. The schema is NOT a blocker; *safe* live emission gates on the cross-repo deps below.
- [x] Cross-repo deps (verified 2026-06-05): bot **#109 CLOSED/COMPLETED** (PR #131 — gateway `/api/v1/ingest` ingest guards landed: body-size/rate/sensitive-data). The Live-emission gate is **lifted**; `GatewaySink` is now real (Entry #71). Remaining bot context: **#73** OPEN (release signing/trust posture); MCP→ToolRequest refactor ongoing. #108 CLOSED. (Prior "bot #99 v1-schema blocker" was a misattribution — SG-2026-06-04-N.)
- [ ] **Live operator-actionable (next)**: an operator configures `GatewaySink(endpoint, token)` against a real gateway to promote a connector to **Live** (the repo delivers the verified seam; the deployment earns Live).

---

*State snapshot maintained by Qor-logic. Run `/qor-status` for a live diagnostic.*
