# SOC 2 Mapping (Trust Service Criteria)

Control alignment, not certification. A SOC 2 attestation is an auditor's
opinion over an operator's system; this maps the repo controls that *support*
the relevant criteria.

| TSC | Criterion | Control | Evidence |
|-----|-----------|---------|----------|
| Security (CC) | Logical access / change control | Branch protection (PR review + status checks), gated cycles, least-privilege workflow permissions. | `GOVERNANCE.md`, `.github/workflows/*` |
| Security (CC) | Vulnerability management | CodeQL, Bandit, dependency-review, pip-audit, Scorecard, Dependabot, TruffleHog. | security + supply-chain gates |
| Security (CC) | Change management / integrity | Every change passes research→plan→**independent audit**→implement→substantiate; recorded in a hash-chained ledger verified in CI. | `governance-gate.yml`, `META_LEDGER` |
| Processing Integrity (PI) | Complete, accurate, authorized processing | Test-functionality gate + FEATURE_INDEX (every feature has a behavioral test, verified in CI); fail-closed verification. | `governance_gate.py`, FEATURE_INDEX |
| Confidentiality (C) | Protect confidential data | Producer sensitive-data screen rejects secrets/PHI/PAN; secret scanning; no canonical persistence. | `sensitive.py` (`FX-SEC-001`), `secret-scan.yml` |
| Availability (A) | — | Operator-owned (deployment/runtime); not a producer-library concern. | n/a |

**Audit-trail export:** the `META_LEDGER` hash chain + `.qor/gates/*` provenance
constitute an exportable, tamper-evident change-and-decision trail suitable as
SOC 2 evidence. **Operator-owned:** the SOC 2 engagement, control period, and
auditor opinion.
