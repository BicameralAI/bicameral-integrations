# Bicameral Integrations

[![CI](https://github.com/BicameralAI/bicameral-integrations/actions/workflows/ci.yml/badge.svg)](https://github.com/BicameralAI/bicameral-integrations/actions/workflows/ci.yml)
[![Secret scan](https://github.com/BicameralAI/bicameral-integrations/actions/workflows/secret-scan.yml/badge.svg)](https://github.com/BicameralAI/bicameral-integrations/actions/workflows/secret-scan.yml)
[![Python 3.13](https://img.shields.io/badge/python-3.13-3776AB.svg)](.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Bicameral Integrations** contains the open-source source adapters, connector parse surfaces, webhook verification helpers, and EM-safe mods that feed reviewable evidence into Bicameral.

Integrations are the expressive edge of the system. They understand external workflow surfaces such as GitHub, Fathom, Linear, Granola, Google Drive, Jira, local files, meetings, and customer-specific sources. They preserve evidence and emit neutral protocol-shaped objects; they do not own canonical state, approve work, or bypass governance.

## Table of Contents

- [What Belongs Here](#what-belongs-here)
- [Architecture](#architecture)
- [Repository Map](#repository-map)
- [Implemented Surface](#implemented-surface)
- [Sister Repositories](#sister-repositories)
- [Safety Contract](#safety-contract)
- [Local Development](#local-development)
- [Documentation Standard](#documentation-standard)
- [Project Governance](#project-governance)

## What Belongs Here

Use this repository for provider-specific parsing, adapter-normalization support, source fixtures, connector tests, webhook verification primitives, and EM-safe advisory mods.

Do not put canonical decision storage, gateway authority, operator secrets, credential resolution, or governance policy enforcement in this repository. Those belong to the local daemon and gateway layer.

## Architecture

```text
External source
GitHub / Fathom / Linear / Granola / Google Drive / Jira / local files
        |
        v
provider connector
        |
        v
adapter.core Observation
        |
        v
adapter.core.normalize(...)
        |
        v
AdapterEmission with source evidence
        |
        v
bicameral-bot gateway and governance review
```

The adapter core owns the neutral object model and validation contract. Connectors own provider field knowledge. Mods remain advisory and operate over emissions without direct authority.

## Repository Map

```text
bicameral-integrations/
|-- adapter/
|   `-- core/                  # Observations, emissions, validation, filters, webhook security
|-- connectors/                # Provider parse surfaces, auth notes, fixtures, tests
|   |-- fathom/
|   |-- github/
|   |-- google_drive/
|   |-- granola/
|   |-- jira/
|   |-- linear/
|   `-- local_directory/
|-- mods/                      # EM-safe advisory mod manifests
|-- docs/                      # Architecture decisions, feature index, governance state
|-- staging/                   # Extraction notes and migration issue drafts
|-- .github/workflows/         # CI and secret scanning
|-- CONTRIBUTING.md
|-- SECURITY.md
|-- GOVERNANCE.md
`-- README.md
```

## Implemented Surface

| Area | Status | Primary Docs | Tests |
| --- | --- | --- | --- |
| Universal adapter normalization | Implemented | [adapter](adapter/README.md), [adapter core](adapter/core/README.md) | `adapter/core/tests/` |
| Sensitive producer screening | Implemented | [adapter core](adapter/core/README.md) | `adapter/core/tests/test_sensitive.py` |
| Webhook signature verification and dedup | Implemented | [adapter core](adapter/core/README.md) | `adapter/core/tests/test_webhook_security.py` |
| GitHub PR parsing | Implemented parse surface; live fetch deferred | [GitHub connector](connectors/github/README.md) | `connectors/github/tests/` |
| Fathom meeting parsing and webhook verification | Implemented parse and verification; live HTTP deferred | [Fathom connector](connectors/fathom/README.md) | `connectors/fathom/tests/` |
| Linear issue webhook parsing and verification | Implemented parse and verification; live GraphQL deferred | [Linear connector](connectors/linear/README.md) | `connectors/linear/tests/` |
| Granola transcript parsing | Implemented parse surface; live polling deferred | [Granola connector](connectors/granola/README.md) | `connectors/granola/tests/` |
| Google Docs parsing | Implemented parse surface; live OAuth/API deferred | [Google Drive connector](connectors/google_drive/README.md) | `connectors/google_drive/tests/` |
| Local-directory file parsing | Implemented parse surface; live scan deferred | [Local-directory connector](connectors/local_directory/README.md) | `connectors/local_directory/tests/` |
| Jira connector | Auth and boundary scaffold | [Jira connector](connectors/jira/README.md) | Pending implementation |
| EM-safe mods | Manifest scaffolds | [mods](mods/README.md) | Manifest review |

## Sister Repositories

| Repository | Role | Relationship |
| --- | --- | --- |
| [`bicameral-bot`](https://github.com/BicameralAI/bicameral-bot) | Local daemon, gateway, review routing, and protocol contracts | Integrations emit toward this gateway and wait for its canonical protocol boundary. |
| [`bicameral-mcp`](https://github.com/BicameralAI/bicameral-mcp) | Agent-facing MCP tools and legacy integration source material | This repo extracts provider-specific adapter and mod material out of MCP while leaving authority in MCP/bot layers. |
| [`bicameral-cloud`](https://github.com/BicameralAI/bicameral-cloud) | Hosted code graph and oracle services | Cloud may consume governed outputs, but it is not the source-adapter host. |

## Safety Contract

Connectors may parse provider payloads, preserve source references, verify webhook authenticity where implemented, deduplicate deliveries, and return neutral observations.

Adapters may normalize observations into `AdapterEmission` objects, validate the emission contract, reject sensitive evidence, and preserve source excerpts for review.

Mods may emit candidates, evidence annotations, hints, dependency signals, advisory governance results, and suggested review commands.

This repository must not write `.bicameral/decisions/*.yaml`, approve signoff, mark compliance resolved, create direct blocking CI results, collapse confidence surfaces into opaque scalar scores, store operator secrets, or bypass gateway governance policy.

## Local Development

Install the local tooling used by CI:

```bash
python -m pip install --upgrade pip ruff mypy pytest
```

Run the complete local gate:

```bash
ruff check adapter connectors
mypy adapter connectors
pytest adapter/core/tests connectors -q
```

Run focused tests while working:

```bash
pytest adapter/core/tests -q
pytest connectors/github/tests -q
pytest connectors/fathom/tests -q
pytest connectors/linear/tests -q
```

## Documentation Standard

Every README in this repository is part of the public engineering contract. Keep documentation current in the same change that alters connector behavior, source modes, auth expectations, test commands, or authority boundaries.

Contributor documentation expectations:

- Include a linked table of contents for every README with more than one section.
- State what is implemented, what is deferred, and where deferred runtime responsibility lives.
- Link to the relevant parent README, code files, fixtures, auth notes, and tests.
- Describe the safety boundary in user-facing terms.
- Avoid undocumented behavior changes; code, fixtures, tests, and docs must move together.

## Project Governance

- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Governance](GOVERNANCE.md)
- [Changelog](CHANGELOG.md)
- [Feature Index](docs/FEATURE_INDEX.md)
- [Architecture Decisions](docs/adr/)
