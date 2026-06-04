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

## Project Governance

- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Changelog](CHANGELOG.md)
