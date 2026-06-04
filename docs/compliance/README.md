# Compliance Mappings

These documents map external frameworks to the **concrete, enforced controls**
in this repository. They are **control-alignment references, not certifications**.
A mapping cites real CI gates, governance artifacts, and code controls as the
evidence for each framework objective; it does not assert legal compliance.

Frameworks are not enforced by per-law CI checkers (there is no `gdpr.yml`).
They are satisfied — to the extent a producer-side library can — by the layered
controls below, exactly as `microsoft/agent-governance-toolkit` does it
(see [SG-2026-06-04-C](../SHADOW_GENOME.md)).

## Control layers (the evidence the mappings cite)

| Layer | Control | Where |
|-------|---------|-------|
| SAST | CodeQL (security-extended), Bandit | `.github/workflows/codeql.yml`, `security-scan.yml` |
| Secret detection | TruffleHog (`--only-verified`) | `.github/workflows/secret-scan.yml` |
| Dependency / supply chain | dependency-review (fail≥moderate + license allowlist), pip-audit, OpenSSF Scorecard, SBOM (SPDX/CycloneDX + attestation), SHA-pinned actions, Dependabot | `dependency-review.yml`, `scorecard.yml`, `sbom.yml`, `.github/dependabot.yml` |
| Governance integrity | hash-chained `META_LEDGER` + `FEATURE_INDEX` re-verified in CI | `scripts/governance_gate.py`, `governance-gate.yml` |
| Provenance / oversight | `ai_provenance` manifests (`human_oversight` PASS/VETO/ABSENT), plan `impact_assessment` | `.qor/gates/*` (local) + sealed ledger entries |
| Data protection | producer sensitive-data screen (secret/PHI/PAN, fail-closed) | `adapter/core/sensitive.py` (`FX-SEC-001`) |
| Authority boundary | read-only connectors → `normalize()`; no canonical writes; fail-closed webhook verification | `adapter/core/`, `connectors/` |
| Change control | gated cycles (research→plan→audit→implement→substantiate) + branch protection | `docs/META_LEDGER.md`, `GOVERNANCE.md` |

## Framework → mapping

| Framework | Mapping | Posture |
|-----------|---------|---------|
| OWASP (Top 10 + Agentic) | [owasp-mapping.md](owasp-mapping.md) | enforced controls |
| NIST AI RMF 1.0 + SSDF (SP 800-218) | [nist-mapping.md](nist-mapping.md) | controls + provenance |
| EU AI Act | [eu-ai-act-mapping.md](eu-ai-act-mapping.md) | transparency + oversight evidence |
| SOC 2 (Trust Service Criteria) | [soc2-mapping.md](soc2-mapping.md) | control mapping + audit trail |
| GDPR / HIPAA (data protection) | [data-protection-mapping.md](data-protection-mapping.md) | applicability + data-handling controls |

**Scope note:** this repository is a *producer-side* integration library (it
emits evidence/candidates to a gateway; it is not the system of record). Several
framework objectives (e.g. data-subject request handling, BAA execution) belong
to the deploying operator and the downstream gateway, not to this package. Those
are marked **operator-owned** in the individual mappings.
