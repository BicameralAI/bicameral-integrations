# Changelog

All notable changes to Bicameral Integrations will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Security

- Purple-team go-live hardening for Linear, Google Drive, and Devin (issues
  #94–#102): disabled provider-redirect following in `UrllibTransport` +
  `GatewaySink` (no-follow opener) so an untrusted 3xx can no longer re-send the
  auth secret cross-host (SSRF/token-exfil); per-leaf FX-SEC-001 screening (no
  cross-field PAN suppression) + `gateway` source url/ref redaction; fail-closed
  on deeply-nested JSON (`RecursionError`) and non-string provider scalars;
  ServiceNow URL host/query injection guard; GatewaySink no longer reflects the
  untrusted gateway response body into errors; runtime-key allowlist + credentialed
  endpoint host-pinning; aggregate item cap (50k) across paginated pages
  (`poll_client` + `graphql_poll`, DOS-1). Locked by 30 Red Team regression gates
  (`tests/redteam/` + the new blocking `red-team.yml` workflow).

### Added

- Operator go-live runbooks (`docs/runbooks/`) — per-connector live-flip
  walkthroughs (Linear, Google Drive, Devin): credentials, config, dry-run →
  gateway live test, wire-gate confirmation, promote/rollback.
- **Devin** connector flip-ready FX-CFG-001 descriptor (`config.json` +
  generated `SETUP.md` + `index.json`) — the third config-descriptor exemplar
  (poll-only; Bearer `cog_` Service-User; operator-templated `base_url`).

- Universal adapter core: provider-neutral `Observation` → `AdapterEmission`
  normalization seam (`adapter/core`), with a producer sensitive-data screen
  (secret/PHI/PAN, fail-closed) and L3 webhook signature verification
  (Svix/Standard-Webhooks + hex HMAC) plus replay dedup.
- Source connector parse surfaces (read-only evidence adapters, ADR-0008):
  GitHub, Fathom, Linear, Granola, local-directory, Google Drive, SARIF, Slack,
  Notion, MCP Registry, Continue, Aider, the Phase-2 security/operational
  evidence connectors — OSV.dev (supply-chain vulnerability aggregator), Sentry
  (runtime issue), and PagerDuty (incident) — Claude Code (developer-AI
  session transcripts), and Jira Cloud (issue webhooks, signature-verified) —
  completing the Phase-1 foundation set.
- **Zendesk** connector (support-ticket evidence — the first support/customer-
  success source): `parse_ticket` (subject-only excerpt, never the PII-dense
  ticket body) + Base64-HMAC webhook signature verification
  (`verify_zendesk_signature` over `timestamp + body`). Live REST/OAuth and a
  PII redaction-and-pass model for live ticket-body ingest are deferred.
- CI governance/security gate ecosystem: governance-integrity gate
  (ledger hash-chain + feature-index), CodeQL, Bandit, OpenSSF Scorecard, SBOM +
  attestation, dependency-review, secret scan, and quality/PR-hygiene gates —
  all SHA-pinned, with six published as reusable `workflow_call` templates.
- Compliance control mappings (OWASP, NIST AI RMF & SSDF, EU AI Act, SOC 2,
  GDPR/HIPAA) and the integration strategy/candidate-catalog/trust-tier docs.
- ADR-0011 proposing Bicameral Review Bot as a first-party, evidence-first PR
  review workflow that can operate without external AI-review rate-limit
  availability.
- Operator-runtime boundary layer (`runtime/`, ADR-0012): a framework-free
  library seam — `EmissionSink`/`SecretResolver` protocols, a reference
  `CollectingSink`, `MappingSecretResolver`, and `deliver_webhook`/`deliver_poll`
  orchestration — that lets an operator host drive a connector's
  ingest → verify → normalize → emit path without this repo becoming a server.
- **Live emission**: `GatewaySink` maps each `AdapterEmission` to the pinned v1
  `IngestRequest` and POSTs it to `/api/v1/ingest` (stdlib `urllib`) now that the
  upstream gateway ingest guards landed. Default-safe (no endpoint → gated),
  fail-closed (re-screens at the emission boundary; only HTTP 201 succeeds; any
  other status or transport fault raises `GatewayEmissionError`), and secret-safe
  (the operator-injected auth token never appears in an error or log). Connectors
  reach **Live** when an operator wires a configured `GatewaySink` against a real
  gateway.
- **Live-poll client** (`runtime/poll_client.py`): the *fetch* half of a poll
  connector's ingest path — the symmetric counterpart of `deliver_webhook`'s
  receive side. `poll(connector, spec, transport, sink)` constructs the
  authenticated request, walks pagination through an injected `HttpTransport`
  (stdlib `UrllibTransport` default), and delegates to `deliver_poll`. Fail-closed
  (non-200 / unparseable / non-dict body / non-list items / poisoned page token /
  blank secret / page + response-size caps all raise `PollError`) and token-safe
  (the operator secret never enters an error or log); the provider response,
  including the pagination token, is treated as untrusted. Reference-wired for
  `anthropic_admin` (aggregate, PII-free) and proven end-to-end against recorded
  response fixtures — the real network call stays operator-run (a mock does not
  promote a connector to Live).
- **Live-poll fan-out (Bearer connectors)**: `BearerAuth` + per-connector specs
  (`runtime/poll_specs.py`) wiring `openai_admin` (Bearer + `last_id`/`after`
  cursor), `copilot` (Bearer; top-level JSON array → per-day), `devin` (Bearer;
  operator-templated org), and `granola` (Bearer; operator-side `since` watermark)
  through the same fail-closed/token-safe poll harness, each proven against recorded
  fixtures. The poll client now accepts a top-level JSON array page (not only an
  object). The secret is resolved by connector `source_id`. `google_drive`
  (`documents.get` + OAuth — a per-resource fetch) and `mcp_registry` (Candidate)
  are disclosed-deferred. Per-connector wire assumptions (envelope key / cursor /
  header version) are recorded in each `auth.md` as the gate before live-network use.
- **Live-poll fan-out (Basic-auth connectors)**: `BasicAuth` (`base64(user:pass)`,
  CR/LF-screened on the raw inputs), **POST-body** request support, and an
  **`OffsetPager`** (offset pagination, stop-on-short-page) wiring `cursor`
  (`POST /teams/daily-usage-data`; key-as-username Basic; PII-free allowlist) and
  `servicenow` (`GET /api/now/table/incident`; `sysparm_offset`/`sysparm_limit`
  pagination; redact-and-pass), each proven against recorded fixtures. The auth
  strategies moved to `runtime/poll_auth.py` (module split). **All 7 buildable poll
  connectors now have the fetch half**; `google_drive` + `mcp_registry` remain
  disclosed-deferred.
- ADR-0012 introducing the connector readiness ladder
  (Candidate → Prototype → Beta → Live). **All 24 connectors** are now **Beta** —
  each promotion earned by a real end-to-end runtime-harness proof against a
  reference sink (signed webhook → `deliver_webhook` → emission for the
  verify-wired connectors; `deliver_poll` → emission for the passive/active
  connectors), with no cross-repo dependency. Live (gateway emission) is now
  operator-actionable (the upstream ingest guards landed).
- Additional source connectors (all Beta, harness-proven): **GitLab**
  (merge-request / issue webhooks; first plaintext `X-Gitlab-Token` shared-secret
  verify, not HMAC), **Confluence** (Cloud page content; verify deferred),
  **GitHub Copilot** (aggregate usage metrics, PII-free), **Cursor** (team usage
  metrics; identity dropped at parse), **Devin** (v3 agentic-session evidence;
  free-text redacted), and **ServiceNow** (ITSM incidents; description redacted,
  caller dropped).
- **PII redaction-and-pass model** (`adapter/core/redaction.py::redact`): scrubs
  secret/PHI/PAN (value-consuming `redact_catalog`) plus email/phone to
  placeholders so PII-dense free-text can be emitted as evidence rather than
  rejected — invariant `detect_sensitive(redact(x)) == []`. Composes with, never
  replaces, the fail-closed FX-SEC-001 screen. Consumed by the ServiceNow and
  Devin connectors; unblocks live Zendesk ticket bodies and Cursor per-developer
  attribution.
- Repository governance and the Qor lifecycle documentation set.

### Changed

- Standardized all connector READMEs to a consistent Modes/Surface/References
  style; added CI/license status badges to the primary README.
- Professional documentation pass across all READMEs: expanded the primary
  README with a value-prop tagline, a project-signal badge row (connectors,
  stdlib-only, mypy, Ruff, Conventional Commits, PRs-welcome, security policy),
  a maturity/footprint/safety/assurance table, and a Design Principles section;
  refreshed every connector README to a confident Beta posture (live ingest
  correctly framed as the deferred boundary); and recovered the `mods/`
  documentation set.
- Bumped `actions/checkout` to v6 and `actions/setup-python` to v6 across CI.
- Fixed the OpenSSF Scorecard CI gate (was `startup_failure`): disabled the
  OIDC-based public-results publish (`publish_results: false`, dropped
  `id-token: write`) and corrected the reusable workflow's top-level
  `permissions` to stay within the caller's grant. The Scorecard analysis and
  its SARIF upload to code-scanning are unchanged; only the public badge
  publish (unused) is dropped. All CI gates are now green.
- Hardened CI workflow token permissions to least privilege: `codeql.yml`,
  `scorecard.yml`, and `sbom.yml` now declare top-level `permissions: contents:
  read` and grant write scopes only at the calling job; SBOM no longer requests
  `contents: write`. Resolves the Scorecard Token-Permissions findings.
- Added a "surface selection (interactivity test)" criterion to the integration
  candidate catalog: read-only evidence sources default to direct API/webhook
  adapters; MCP servers are reserved for interactive agent action.

### Security

- Wired webhook signature verification + best-effort delivery dedup into the
  **GitHub** (`X-Hub-Signature-256`), **Slack** (`v0` signing over
  `v0:{ts}:{body}` + 5-minute replay window), and **Notion**
  (`X-Notion-Signature`, prefix-pinned) connectors, adding a `verify_slack_signature`
  primitive. All fail-closed and constant-time; signatures verified over the raw
  body before parsing. GitHub/Slack/Notion join the verify-wired Beta set
  (7 Beta connectors total).
- Wired live webhook signature verification + best-effort delivery dedup
  (fail-closed, constant-time) into the Sentry and PagerDuty connectors —
  including a new multi-signature (`v1=…,v1=…` rotation) HMAC primitive for
  PagerDuty. Sentry/PagerDuty join Fathom/Linear as verify-wired connectors.
- Fixed an incomplete URL host check in the GitHub connector
  (`can_handle_ref`) that matched look-alike hosts (e.g. `github.com.evil.com`);
  now validates the parsed host exactly. Resolves CodeQL
  `py/incomplete-url-substring-sanitization`.
- SHA-pinned the remaining tagged GitHub Actions in `ci.yml` and `secret-scan.yml`
  (supply-chain hardening; resolves the OpenSSF Scorecard pinned-dependencies
  findings).

### Security

- Adversarial red-team of the connector/adapter/runtime code (GH #50-#61). Cycle A
  fixed three documented-guarantee violations: the FX-SEC-001 sensitive screen now
  covers every gateway-wire-bound field (`source_id`/`source_ref.url`/`ref`), so a
  secret embedded in a provider URL/ref/id can no longer be forwarded in cleartext
  (#52); rejected-emission errors no longer carry a raw PAN/PHI value (#53); and
  `GatewaySink` rejects CR/LF in the operator token/headers and never lets an
  unexpected error echo the token (#54). DoS/ReDoS and replay findings
  (#50/#51/#55/#56/#57/#59/#60) are tracked for hardening before any Live deployment.

### Security (red-team Cycle B — DoS/robustness hardening, GH #50/#51/#55/#56/#57/#58/#59)

- Fixed two ReDoS surfaces: the Confluence tag stripper (`<[^<>]*>`) and the email
  redactor (RFC-bounded quantifiers) are now linear (a 200 KB hostile payload went from
  ~15 s to ~20 ms; no email match-set regression). `deliver_webhook` caps the body at 1 MiB
  and the 9 webhook connectors catch `ValueError` so a >4300-digit JSON int fails closed
  instead of crashing. GitHub/ServiceNow parse surfaces guard non-dict/non-str fields;
  fathom `verify()` fails closed on malformed header types; Cursor redacts its free-text
  `day`/`mostUsedModel`; and all 26 connectors' `observations()` reject a non-dict payload.
  Parse surfaces are now safe to expose to hostile payloads (the gate before any Live deployment).

### Security (red-team Cycle C — replay + nits, GH #60/#61)

- The 4 windowless webhook providers (Zendesk/Jira/Sentry/PagerDuty) fall back to a
  body-hash dedup key when a delivery carries no id, closing the id-less unbounded-replay
  vector without dropping events (the eviction/TTL replay window is an inherent bounded-cache
  property, documented on `DeliveryDedupCache`). The emission contract now rejects a
  zero-width-only excerpt (treats Unicode format chars as blank) and bounds `source_id` to
  128 chars. Completes the security red-team (Cycles A/B/C, GH #50-#61).
