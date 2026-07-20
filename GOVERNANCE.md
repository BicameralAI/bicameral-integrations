# Project Governance

## Project

Bicameral Integrations

## Maintainers

BicameralAI maintainers steward repository direction, review contributions, and
preserve the authority boundaries documented in `README.md` and `docs/adr/`.

## Product authority boundary

This is the public, product-facing governance statement. It describes what the
integrations in this repository are permitted to do — not how the project is
developed internally.

- Source adapters and EM-safe mods emit candidates, evidence, hints, signals, and
  advisories through protocol-compatible paths. **They never write canonical state
  directly** ([ADR-0008](docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md)).
- Trust-tiered governance decides how emitted evidence routes to review, advisory
  state, or enforcement downstream ([ADR-0009](docs/adr/0009-trust-tiered-integration-governance.md)).
- Architecture decisions are recorded in `docs/adr/`.

## Development process

The project is developed under a controlled, reviewed process with security review;
every change lands through pull request with required review and CI security/supply-chain
checks. The internal contributor development process — including how contributors bring
their own local tooling — is documented for contributors in
[`CONTRIBUTING.md`](CONTRIBUTING.md) and [`AGENTS.md`](AGENTS.md). Those are contributor
references, not a dependency or required concept for using these integrations.

## Branch Protection Plan

The default branch should be protected with:

- Pull request review before merge
- Status checks for tests and secret scanning
- Restrict force pushes on `main` and release branches
- Require branch lineage from `origin/main` before opening release PRs

## Contribution Guidelines

See `CONTRIBUTING.md`.

## Code of Conduct

See `CODE_OF_CONDUCT.md`.

## Security Policy

See `SECURITY.md`.
