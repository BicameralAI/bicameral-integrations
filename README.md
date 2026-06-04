# Bicameral Integrations

[![CI](https://github.com/BicameralAI/bicameral-integrations/actions/workflows/ci.yml/badge.svg)](https://github.com/BicameralAI/bicameral-integrations/actions/workflows/ci.yml)
[![Governance Gate](https://github.com/BicameralAI/bicameral-integrations/actions/workflows/governance-gate.yml/badge.svg)](https://github.com/BicameralAI/bicameral-integrations/actions/workflows/governance-gate.yml)
[![CodeQL](https://github.com/BicameralAI/bicameral-integrations/actions/workflows/codeql.yml/badge.svg)](https://github.com/BicameralAI/bicameral-integrations/actions/workflows/codeql.yml)
[![Security Scan](https://github.com/BicameralAI/bicameral-integrations/actions/workflows/security-scan.yml/badge.svg)](https://github.com/BicameralAI/bicameral-integrations/actions/workflows/security-scan.yml)
[![OpenSSF Scorecard](https://github.com/BicameralAI/bicameral-integrations/actions/workflows/scorecard.yml/badge.svg)](https://github.com/BicameralAI/bicameral-integrations/actions/workflows/scorecard.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)

**Bicameral Integrations** contains open-source source adapters and EM-safe mods for Bicameral.

Integrations are the expressive edge of the system. They understand Jira, Linear, Slack, Notion, GitHub, support email, meetings, and customer-specific workflows. They do not own canonical state.

## Key Features

- **Source adapters** – transform external tool payloads into typed Bicameral objects.
- **EM-safe mods** – lightweight YAML/prompt/fixture packages for dependency risk, security mentions, routing hints, and review suggestions.
- **Gateway compatibility** – every adapter targets `bicameral-bot/protocol/` contracts.
- **Source evidence preservation** – adapters preserve excerpts, refs, source type, timestamps, and prompt/manifest versions where relevant.
- **Trust-tier configuration** – high-signal sources can auto-create candidates; noisy sources can require manual gating.

## High-level Architecture

```text
External source
Jira / Linear / Slack / Notion / GitHub / email / meetings
        │
        ▼
bicameral-integrations adapter or mod
        │ emits typed protocol objects
        ▼
bicameral-bot gateway
        │
        ▼
local daemon governance + review + storage adapter
```

## Repository Layout

```text
├── adapter/                 # Universal adapter: neutral object model + normalization pipeline
│   └── core/                # Shared contracts (Observation, AdapterEmission, capabilities)
├── connectors/              # Provider-facing parse surfaces (one folder per source)
├── mods/                    # EM-safe advisory mods and fixtures
├── docs/                    # Governance artifacts, ADRs, integration strategy, compliance mappings
├── scripts/                 # Governance gate + CI helper scripts (with tests/)
├── .github/workflows/       # CI gates + reusable (`workflow_call`) gate templates (_reusable-*.yml)
└── README.md                # You are here
```

## Connectors

Each connector is a provider-facing **parse surface** — `parse_*(payload) -> Observation` plus a `<Provider>Connector` class — feeding the [universal adapter](adapter/README.md) (`pipeline.normalize()`). All connectors are read-only evidence adapters; they never write canonical state ([ADR-0008](docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md)). Readiness follows the [connector readiness ladder](docs/adr/0012-connector-readiness-ladder-and-live-ingest-runtime.md) (`Candidate → Prototype → Beta → Live`); **Beta** = proven end-to-end through the [`runtime/`](runtime/README.md) harness against a reference sink (signed webhook → verify → normalize → emit), with no cross-repo dependency. **Live** (gateway emission) is gated on `bicameral-bot` #109. See [`connectors/README.md`](connectors/README.md) for the full index.

### Beta — verify-wired, harness-proven

| Connector | Source evidence | Modes · verify |
|---|---|---|
| [github](connectors/github/) | Pull requests → Observations | webhook (`X-Hub-Signature-256`) + active |
| [linear](connectors/linear/) | Issue change events | webhook (HMAC + 60 s replay) + active |
| [fathom](connectors/fathom/) | Meeting transcripts + summaries | webhook (Svix) + passive |
| [sentry](connectors/sentry/) | Runtime issue/error events | webhook (HMAC) |
| [pagerduty](connectors/pagerduty/) | Incident / on-call events | webhook (multi-signature `v1=`) |
| [slack](connectors/slack/) | Channel messages (Events API) | webhook (`v0` + 5 m replay) |
| [notion](connectors/notion/) | Page objects | webhook (`X-Notion-Signature`) + active |

### Prototype — parse surface (live ingest / verify deferred per `auth.md`)

| Connector | Source evidence | Mode · tier |
|---|---|---|
| [jira](connectors/jira/) | Jira Cloud issue webhooks (verify-wired, `sha256=`) | webhook + active · T1 |
| [granola](connectors/granola/) | Granola meeting transcripts | passive · T1 |
| [local_directory](connectors/local_directory/) | Local files (path/content/modified) | passive · T1 |
| [google_drive](connectors/google_drive/) | Google Docs documents | active · T1 |
| [sarif](connectors/sarif/) | SARIF 2.1.0 static-analysis results | passive · T0 |
| [mcp_registry](connectors/mcp_registry/) | MCP Registry `server.json` entries | active · T1 |
| [continue_dev](connectors/continue_dev/) | Continue dev-data events | passive · T0 |
| [aider](connectors/aider/) | Aider-attributed git commits | passive · T0 |
| [claude_code](connectors/claude_code/) | Claude Code session transcripts | passive · T0 |
| [osv](connectors/osv/) | OSV.dev vulnerability records (no-auth aggregator) | active · T1 |

Selection criteria and trust tiers: [Integration Candidate Catalog](docs/INTEGRATION_CANDIDATE_CATALOG.md) · [Trust Tier Model](docs/TRUST_TIER_MODEL.md). Provider-evidence vs. agent-action surface choice: the [interactivity-test triage](docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md) (read-only evidence → this repo; interactive action → `bicameral-mcp`).

## Planned Mods

Mods are EM-safe advisory packages (under active build by a parallel track) that read evidence and emit hints/advisories — never canonical decisions (see [Mod Safety Contract](#mod-safety-contract)). Each links to its scope spec.

| Mod | Advises on |
|---|---|
| [adapter_contract](mods/adapter_contract/) | Evidence-shape & contract-preservation risks in connector/adapter output |
| [authority_boundary](mods/authority_boundary/) | Changes that may cross authority, trust-tier, or canonical-state boundaries |
| [code_review_risk](mods/code_review_risk/) | PR-level review risk (the first mod family behind the Bicameral Review Bot, [ADR-0011](docs/adr/0011-bicameral-review-bot.md)) |
| [connector_freshness](mods/connector_freshness/) | Stale provider assumptions in connector docs, fixtures, auth notes, parser scope |
| [data_classification](mods/data_classification/) | Classifying sensitive evidence before routing / outbound notification |
| [decision_drift](mods/decision_drift/) | New evidence that conflicts with recorded decisions, ADRs, trust tiers |
| [dependency_risk](mods/dependency_risk/) | Dependency upgrade, pin, SDK-drift, compatibility-risk signals |
| [noisy_source_gate](mods/noisy_source_gate/) | Manual-gating high-noise sources (Slack/email/meetings) unless trust is raised |
| [ownership_routing](mods/ownership_routing/) | Reviewer-lens & domain-ownership suggestions from changed paths + evidence |
| [security_mentions](mods/security_mentions/) | Auth, token, secret, PII, webhook-verification, transport-exposure signals |
| [source_trust_calibration](mods/source_trust_calibration/) | Calibrating source trust by provenance, type, historical noise, sensitivity |
| [test_adequacy](mods/test_adequacy/) | Missing/weak tests around changed behavior, parsing, fixtures, gates |
| [webhook_risk](mods/webhook_risk/) | Webhook safety: signature verification, replay, schema, idempotency, side effects |

## Related Repositories

- [`bicameral-bot`](https://github.com/BicameralAI/bicameral-bot) – local daemon/gateway and embedded protocol contracts.
- [`bicameral-mcp`](https://github.com/BicameralAI/bicameral-mcp) – agent-facing tool surface; not a source-adapter repo.
- [`bicameral-cloud`](https://github.com/BicameralAI/bicameral-cloud) – hosted code graph/oracle; not the adapter host by default.

## Mod Safety Contract

Mods may emit candidates, evidence, hints, dependency signals, advisories, and suggested review commands. Mods may not write `.bicameral/decisions/*.yaml`, approve signoff, mark compliance resolved, create blocking CI results directly, collapse confidence surfaces, or bypass governance policy.

## Testing

```bash
pytest -q adapter/core/tests connectors scripts/tests
```

Governance integrity (ledger hash-chain + feature-index test paths) is verified
separately and in CI:

```bash
python scripts/governance_gate.py
```

## CI Gates

Every change runs through SHA-pinned GitHub Actions gates, several of which are
also published as reusable `workflow_call` templates (`.github/workflows/_reusable-*.yml`)
for the wider Bicameral ecosystem:

- **lint + type + test** (ruff, mypy, pytest) · **Governance Gate** (ledger hash-chain + feature-index)
- **CodeQL** · **Bandit** · **Security Scan** · **OpenSSF Scorecard** · **SBOM + attestation** · **dependency-review** · **secret scan** (TruffleHog)
- **Quality** (workflow-YAML lint, codespell, SPDX headers) · **PR hygiene** (conventional title)

Framework control mappings (OWASP, NIST AI RMF & SSDF, EU AI Act, SOC 2, GDPR/HIPAA)
live in [`docs/compliance/`](docs/compliance/) — control alignment, not certification.

## Documentation

- **Architecture & decisions**: [ADRs](docs/adr/) — incl. [0004 adapter boundary](docs/adr/0004-integration-adapter-boundary.md), [0005 emission contract](docs/adr/0005-adapter-emission-contract.md), [0006 active/passive/webhook modes](docs/adr/0006-active-passive-webhook-modes.md), [0008 evidence-not-authority](docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md), [0009 trust-tiered governance](docs/adr/0009-trust-tiered-integration-governance.md), [0012 readiness ladder + runtime boundary](docs/adr/0012-connector-readiness-ladder-and-live-ingest-runtime.md)
- **Contracts**: [Governed Adapter Contract](docs/GOVERNED_ADAPTER_CONTRACT.md) · [Trust Tier Model](docs/TRUST_TIER_MODEL.md) · [Data Classification & Redaction](docs/DATA_CLASSIFICATION_AND_REDACTION.md)
- **Strategy & catalog**: [Integration Strategy & Candidate Harvesting](docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md) · [Integration Candidate Catalog](docs/INTEGRATION_CANDIDATE_CATALOG.md) · [Integration Docs Index](docs/INTEGRATION_DOCS_INDEX.md)
- **Feature & state**: [Feature Index](docs/FEATURE_INDEX.md) (every feature → a test) · [System State](docs/SYSTEM_STATE.md) · [Backlog](docs/BACKLOG.md)
- **Governance internals**: [Governance Index](docs/GOVERNANCE_INDEX.md) · [Meta Ledger](docs/META_LEDGER.md) (hash-chained) · [Shadow Genome](docs/SHADOW_GENOME.md) (lessons) · [Compliance mappings](docs/compliance/) · [Ecosystem gate adoption](docs/ecosystem/)
- **Components**: [adapter/](adapter/README.md) · [connectors/](connectors/README.md) · [runtime/](runtime/README.md)

## Project Governance

- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Changelog](CHANGELOG.md)
