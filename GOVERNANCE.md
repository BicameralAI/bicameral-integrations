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

## Process Governance (three layers)

Repository **process** governance is layered:

- **Shared process (bic-logic)** — factory-owned doctrine, owned upstream in
  `bicameral-factory` and consumed here. This is the **one mandatory layer**: the contract
  every PR must satisfy.
- **Sibling tools (registry)** — any local process, governance, or AI tooling a contributor
  uses is a *registered sibling*: leak-guarded, never tracked, never referenced. The registry
  is [`docs/governance/SIBLINGS.md`](docs/governance/SIBLINGS.md). The maintainer's own tooling
  is itself a registered sibling, not a requirement on contributors.

Contributors are free to bring their own tooling — see `CONTRIBUTING.md` → *Bring your own
tools*. This is repo/process governance only; it never produces product Decisions, gates, or
compliance outcomes.

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
