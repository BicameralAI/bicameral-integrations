# NIST Mapping — AI RMF 1.0 + SSDF (SP 800-218)

Control alignment, not certification.

## AI RMF 1.0

| Function | How this repo aligns | Evidence |
|----------|----------------------|----------|
| GOVERN | Documented governance doctrine + gated cycles; roles separated (Analyst/Governor/Judge/Specialist). | `GOVERNANCE.md`, `META_LEDGER`, gate artifacts |
| MAP | Research phase verifies external APIs/risks before build; plan declares `impact_assessment` for L3. | `docs/research-brief-*`, `plan-*` |
| MEASURE | Independent adversarial audit each cycle (Option-B reviewer); test functionality gate; SAST. | audit gate entries, `codeql.yml` |
| MANAGE | VETO loop blocks implementation until risks resolved; tamper-evident ledger records every decision. | Entries #11/#15/#19 (VETO→PASS) |

## SSDF (SP 800-218) practices

| Practice group | Control | Evidence |
|----------------|---------|----------|
| PO (Prepare Org) | Security policy, governance index, branch protection. | `SECURITY.md`, `GOVERNANCE_INDEX.md` |
| PS (Protect Software) | SHA-pinned actions, SBOM + attestation, hash-chained ledger integrity gate. | `sbom.yml`, `governance-gate.yml` |
| PW (Produce Well-Secured) | SAST (CodeQL/Bandit), secret screen, fail-closed crypto, TDD + audit before merge. | `security-scan.yml`, `sensitive.py` |
| RV (Respond to Vulnerabilities) | dependency-review, pip-audit, Dependabot, Scorecard. | dependency/supply-chain gates |

SSDF practices are mapped to controls in the table above. Per-decision attestation
is the QOR `ai_provenance` manifest on each gate artifact, which records
`system`, `version`, `model_family`, `human_oversight`, and `ts` — establishing
*who/what/when* a practice was applied. (It does not emit per-practice SSDF tags;
the practice→control linkage is this document.)
