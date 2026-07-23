# SOC 2 Mapping (Trust Service Criteria)

Control alignment, not certification. A SOC 2 attestation is an auditor's
opinion over an operator's system; this maps the repo controls that *support*
the relevant criteria.

| TSC | Criterion | Control | Evidence |
|-----|-----------|---------|----------|
| Security (CC) | Logical access / change control | Branch protection (PR review + status checks), gated cycles, least-privilege workflow permissions. Desired vs observed branch/ruleset state is declared in the repo descriptor; observed state is `unverified` until backed by live org-ruleset evidence. | `GOVERNANCE.md`, `.github/workflows/*`, `.bicameral/repo-governance.yaml` (`branch_protection` + `observed_state`) |
| Security (CC) | Vulnerability management | CodeQL, Bandit, dependency-review, pip-audit, Scorecard, Dependabot, TruffleHog. | security + supply-chain gates |
| Security (CC) | Change management / integrity | Every change passes research→plan→**independent audit**→implement→substantiate; recorded in a hash-chained ledger verified in CI. | `governance-gate.yml`, `META_LEDGER` |
| Security (CC) | Software / release inventory boundary | Deterministic, fail-closed release-artifact inventory: the customer archive carries no Factory-internal or contributor-only development material (`customer_distribution` boundary). Runs at exact HEAD. | `scripts/check_release_inventory.py`, `.gitattributes` `export-ignore`, `.bicameral/repo-governance.yaml` (`customer_distribution`) |
| Security (CC) | Inter-repo contract provenance | Shared inter-repo contracts pin an immutable upstream commit + content hash with producer/consumer ownership; drift is detected in CI. | `docs/governance/PIN.json`, `scripts/validate_governance_pin.py`, `scripts/validate_ingest_schema_pin.py` |
| Processing Integrity (PI) | Complete, accurate, authorized processing | Test-functionality gate + FEATURE_INDEX (every feature has a behavioral test, verified in CI); fail-closed verification. | `governance_gate.py`, FEATURE_INDEX |
| Confidentiality (C) | Protect confidential data | Producer sensitive-data screen rejects secrets/PHI/PAN; secret scanning; no canonical persistence. | `sensitive.py` (`FX-SEC-001`), `secret-scan.yml` |
| Availability (A) | — | Operator-owned (deployment/runtime); not a producer-library concern. | n/a |

**Audit-trail export:** the `META_LEDGER` hash chain + local gate-artifact provenance
constitute an exportable, tamper-evident change-and-decision trail suitable as
SOC 2 evidence. **Operator-owned:** the SOC 2 engagement, control period, and
auditor opinion.

**Live-evidence caveat:** the artifact-boundary check runs deterministically at exact
HEAD, but wiring it as a required status check and capturing live branch/ruleset evidence
(so `observed_state` can move from `unverified` to a timestamped receipt) is a governance-owner
follow-up — see `.bicameral/repo-governance.yaml` (`observed_state`).
