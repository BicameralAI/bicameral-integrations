# Changelog

All notable changes to Bicameral Integrations will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added

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
  Gateway emission is a stubbed `GatewaySink` that fails closed until the
  upstream ingest guards land.
- ADR-0012 introducing the connector readiness ladder
  (Candidate → Prototype → Beta → Live). **All 18 connectors** are now **Beta** —
  each promotion earned by a real end-to-end runtime-harness proof against a
  reference sink (signed webhook → `deliver_webhook` → emission for the
  verify-wired connectors; `deliver_poll` → emission for the passive/active
  connectors), with no cross-repo dependency. Live (gateway emission) remains
  gated on the upstream ingest guards.
- Repository governance and the Qor lifecycle documentation set.

### Changed

- Standardized all connector READMEs to a consistent Modes/Surface/References
  style; added CI/license status badges to the primary README.
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
