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
  Notion, MCP Registry, Continue, and Aider (plus a Jira scaffold).
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
