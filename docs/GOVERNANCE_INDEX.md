# Governance Index

**Last Reviewed**: 2026-06-04

A single authoritative map of every governance artifact in this project, organized
into six freshness tiers with explicit drift contracts. A stale entry here is
itself a Tier 1 drift bug, so the index is self-policing. See
`qor/references/doctrine-governance-index.md` for the model and contracts.

## Tier 1 — Canonical Source

MUST be current at every cycle close. Drift signal: wrong version / wrong state / missing recent entries.

| Artifact | Path | Freshness marker |
|----------|------|------------------|
| Meta Ledger | `docs/META_LEDGER.md` | latest sealed entry (#44) |
| Shadow Genome | `docs/SHADOW_GENOME.md` | latest narrative entry |
| System State | `docs/SYSTEM_STATE.md` | latest phase snapshot |
| Concept | `docs/CONCEPT.md` | stable |
| Domain glossary | `CONTEXT.md` | stable vocabulary |
| Architecture Plan | `docs/ARCHITECTURE_PLAN.md` | stable |
| Backlog | `docs/BACKLOG.md` | open items current |
| Feature Index | `docs/FEATURE_INDEX.md` | every feature has a test |
| Changelog | `CHANGELOG.md` | latest release stamped |
| README | `README.md` | badges current |

## Tier 2 — Doctrine & Policy

Stable; changes are explicit doctrine events. Drift signal: rules contradict each other or operator memory.

| Artifact | Path |
|----------|------|
| Security policy | `SECURITY.md` |
| Governance policy | `GOVERNANCE.md` |
| Contribution guide | `CONTRIBUTING.md` |
| Code of conduct | `CODE_OF_CONDUCT.md` |
| Governed adapter contract | `docs/GOVERNED_ADAPTER_CONTRACT.md` |
| Trust tier model | `docs/TRUST_TIER_MODEL.md` |
| Data classification & redaction | `docs/DATA_CLASSIFICATION_AND_REDACTION.md` |

## Tier 3 — Active Initiative

Live until close; ages out at substantiate. Drift signal: shipped feature still tracked as pending.

| Artifact | Path | Opened |
|----------|------|--------|
| _(none — session state under `.qor/session/` is local/untracked)_ | — | — |

## Tier 4 — Per-Plan Artifact

Live for plan duration; archived at substantiate. Drift signal: plan shipped but artifact still presents as open.

| Artifact | Path | Plan |
|----------|------|------|
| _(none tracked — `plan-*.md` are local drafts, gitignored)_ | — | — |

## Tier 5 — Reference Material

Informational, slow-drift. Drift signal: factual claims diverge from current code.

| Artifact | Path |
|----------|------|
| Architecture decision records | `docs/adr/0004..0011-*.md` |
| Integration candidate catalog | `docs/INTEGRATION_CANDIDATE_CATALOG.md` |
| Integration docs index | `docs/INTEGRATION_DOCS_INDEX.md` |
| Integration strategy & candidate harvesting | `docs/INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md` |
| Adapter-contract research brief | `docs/research-brief-adapter-contract-2026-06-02.md` |
| Security & governance research brief | `docs/research-brief-security-governance-alignment-2026-06-03.md` |
| Fathom + Linear connectors research brief | `docs/research-brief-fathom-linear-connectors-2026-06-03.md` |
| Webhook verification research brief | `docs/research-brief-webhook-verification-2026-06-04.md` |
| CI governance gates research brief | `docs/research-brief-ci-governance-gates-2026-06-04.md` |
| Phase-1 connectors research brief | `docs/research-brief-connectors-phase1-2026-06-04.md` |
| Developer-AI connectors (Continue + Aider) research brief | `docs/research-brief-connectors-dev-tools-2026-06-04.md` |
| Connector value-add (net-new candidates) research brief | `docs/research-brief-connector-value-add-2026-06-04.md` |
| Phase-2 connectors (OSV/Sentry/PagerDuty) research brief | `docs/research-brief-connectors-phase2-2026-06-04.md` |
| Webhook hardening (Sentry/PagerDuty signature schemes) research brief | `docs/research-brief-webhook-hardening-2026-06-04.md` |
| Compliance mappings (OWASP/NIST/EU-AI-Act/SOC2/GDPR+HIPAA) | `docs/compliance/` |
| Reusable gates research brief | `docs/research-brief-reusable-gates-2026-06-04.md` |
| Ecosystem gate-adoption guide | `docs/ecosystem/consuming-gates.md` |
| AGT sidecar evaluation (bicameral-bot) | `docs/ecosystem/agt-sidecar-evaluation.md` |

## Tier 6 — Archived

Frozen historical record. Drift signal: none (frozen).

| Archive | Path |
|---------|------|
| _(none yet)_ | — |

## How to add a governance artifact

1. Create the file in the same commit that registers it here.
2. Add a row to the tier whose freshness contract matches the file's lifecycle.
3. Refresh **Last Reviewed** above.

## How to retire a governance artifact

1. Move the file to the Tier 6 archive path.
2. Move its row from its live tier to Tier 6 (or delete it if superseded).
3. Refresh **Last Reviewed** above.
