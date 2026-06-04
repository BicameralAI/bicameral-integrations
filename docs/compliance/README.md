# Compliance Mappings

These documents map external frameworks to the concrete, enforced controls in this repository. They are control-alignment references, not certifications.

A mapping cites real CI gates, governance artifacts, and code controls as evidence for each framework objective. It does not assert legal compliance.

## Table of Contents

- [Scope](#scope)
- [Control Layers](#control-layers)
- [Framework Mappings](#framework-mappings)
- [Evidence Standard](#evidence-standard)
- [Operator-Owned Responsibilities](#operator-owned-responsibilities)
- [Related Documentation](#related-documentation)

## Scope

This repository is a producer-side integration library. It emits evidence and candidates to a gateway; it is not the system of record and does not own downstream governance approval, data-subject workflows, customer contracts, or operational incident response.

Frameworks are not enforced by per-law CI checkers. There is no `gdpr.yml`. They are satisfied, to the extent a producer-side library can satisfy them, by layered controls that are documented and tested here.

These mappings follow the same control-alignment posture as `microsoft/agent-governance-toolkit`; see [SG-2026-06-04-C](../SHADOW_GENOME.md).

## Control Layers

| Layer | Control | Evidence |
| --- | --- | --- |
| SAST | CodeQL security-extended and Bandit | `.github/workflows/codeql.yml`, `.github/workflows/security-scan.yml` |
| Secret detection | TruffleHog with verified-secret filtering | `.github/workflows/secret-scan.yml` |
| Dependency and supply chain | Dependency review, pip-audit, OpenSSF Scorecard, SBOM, pinned actions, Dependabot | `.github/workflows/dependency-review.yml`, `.github/workflows/scorecard.yml`, `.github/workflows/sbom.yml`, `.github/dependabot.yml` |
| Governance integrity | Hash-chained `META_LEDGER` and `FEATURE_INDEX` verification | `scripts/governance_gate.py`, `.github/workflows/governance-gate.yml` |
| Provenance and oversight | `ai_provenance` manifests, human oversight verdicts, plan impact assessments | `.qor/gates/*` and sealed ledger entries |
| Data protection | Producer sensitive-data screen for secrets, PHI, and PAN evidence | `adapter/core/sensitive.py`, `FX-SEC-001` |
| Authority boundary | Read-only connectors, adapter normalization, no canonical writes, fail-closed webhook verification | `adapter/core/`, `connectors/` |
| Change control | Gated research, planning, audit, implementation, and substantiation cycles | `docs/META_LEDGER.md`, `GOVERNANCE.md` |

## Framework Mappings

| Framework | Mapping | Posture |
| --- | --- | --- |
| OWASP Top 10 and Agentic guidance | [owasp-mapping.md](owasp-mapping.md) | Enforced controls |
| NIST AI RMF 1.0 and SSDF SP 800-218 | [nist-mapping.md](nist-mapping.md) | Controls and provenance |
| EU AI Act | [eu-ai-act-mapping.md](eu-ai-act-mapping.md) | Transparency and oversight evidence |
| SOC 2 Trust Service Criteria | [soc2-mapping.md](soc2-mapping.md) | Control mapping and audit trail |
| GDPR and HIPAA data protection | [data-protection-mapping.md](data-protection-mapping.md) | Applicability and data-handling controls |

## Evidence Standard

Compliance claims in this directory must cite concrete repository evidence:

- Workflow files, scripts, code controls, or tests.
- Governance artifacts that establish decision history.
- Source files that enforce boundaries or reject unsafe inputs.
- Explicit operator-owned notes where the repository cannot enforce the framework objective itself.

Do not add claims that rely only on intent, roadmap items, or undocumented manual practice.

## Operator-Owned Responsibilities

Several framework objectives belong to the deploying operator and downstream gateway, not to this package. Examples include data-subject request handling, business associate agreements, customer-specific retention policy, production access control, incident response, and final compliance signoff.

Those responsibilities must be marked operator-owned in the individual mappings.

## Related Documentation

- [Repository README](../../README.md)
- [Security Policy](../../SECURITY.md)
- [Governance](../../GOVERNANCE.md)
- [Feature Index](../FEATURE_INDEX.md)
- [System State](../SYSTEM_STATE.md)
