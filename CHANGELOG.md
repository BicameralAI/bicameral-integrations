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
  Notion, MCP Registry, Continue, Aider, and the Phase-2 security/operational
  evidence connectors — OSV.dev (supply-chain vulnerability aggregator), Sentry
  (runtime issue), and PagerDuty (incident) — plus a Jira scaffold.
- CI governance/security gate ecosystem: governance-integrity gate
  (ledger hash-chain + feature-index), CodeQL, Bandit, OpenSSF Scorecard, SBOM +
  attestation, dependency-review, secret scan, and quality/PR-hygiene gates —
  all SHA-pinned, with six published as reusable `workflow_call` templates.
- Compliance control mappings (OWASP, NIST AI RMF & SSDF, EU AI Act, SOC 2,
  GDPR/HIPAA) and the integration strategy/candidate-catalog/trust-tier docs.
- ADR-0011 proposing Bicameral Review Bot as a first-party, evidence-first PR
  review workflow that can operate without external AI-review rate-limit
  availability.
- Repository governance and the Qor lifecycle documentation set.

### Changed

- Standardized all connector READMEs to a consistent Modes/Surface/References
  style; added CI/license status badges to the primary README.
- Bumped `actions/checkout` to v6 and `actions/setup-python` to v6 across CI.
- Added a "surface selection (interactivity test)" criterion to the integration
  candidate catalog: read-only evidence sources default to direct API/webhook
  adapters; MCP servers are reserved for interactive agent action.

### Security

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
