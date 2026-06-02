# Project Governance

## Project

Bicameral Integrations

## Maintainers

BicameralAI maintainers steward repository direction, review contributions, and
preserve the authority boundaries documented in `README.md` and `docs/adr/`.

## Decision Making

Architecture decisions are recorded in `docs/adr/`. Source adapters and EM-safe
mods must emit candidates, evidence, hints, signals, and advisories through
protocol-compatible paths; they must not write canonical state directly.

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
