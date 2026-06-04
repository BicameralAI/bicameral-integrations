# OWASP Mapping

Control alignment, not certification. Covers the OWASP Top 10 (2021) subset
relevant to a producer-side library plus the OWASP Agentic/LLM risks that touch
our ingest surface.

## Web Top 10 (2021) — relevant subset

| Risk | Control in this repo | Evidence |
|------|----------------------|----------|
| A01 Broken Access Control | Connectors are read-only parse surfaces; no canonical writes (authority boundary, ADR-0004). Gateway/governance owns authorization. | `adapter/core/contracts.py`, `connectors/*/connector.py` |
| A02 Cryptographic Failures | Webhook verification uses constant-time `hmac.compare_digest`, HMAC-SHA256; fail-closed; no custom crypto. | `adapter/core/webhook_security.py`, SG-2026-06-04-B |
| A03 Injection | No `eval`/`exec`/`shell=True`/SQL; CodeQL + Bandit SAST gate every PR. | `codeql.yml`, `security-scan.yml` |
| A04 Insecure Design | Fail-closed verification; producer non-authoritative by construction; gated design cycles. | `webhook_security.py`, `META_LEDGER` |
| A05 Security Misconfiguration | SHA-pinned actions (all gate workflows added this cycle); least-privilege workflow `permissions`; secret scanning. Legacy `ci.yml`/`secret-scan.yml` (incl. `trufflehog@main`) pin in a tracked follow-up (BACKLOG). | gate `.github/workflows/*` |
| A06 Vulnerable Components | dependency-review (fail≥moderate), pip-audit, Dependabot, SBOM. | `dependency-review.yml`, `security-scan.yml`, `sbom.yml` |
| A08 Software/Data Integrity | SHA-pinned actions + SBOM attestation + hash-chained governance ledger verified in CI. | `sbom.yml`, `governance-gate.yml` |
| A09 Logging/Monitoring | Tamper-evident `META_LEDGER` audit trail; provenance manifests. | `scripts/governance_gate.py` |

## Agentic / LLM risks (ingest surface)

| Risk | Control | Evidence |
|------|---------|----------|
| Improper Output Handling / Data Leakage | Producer sensitive-data screen rejects secrets/PHI/PAN before emission (HARD gate). | `adapter/core/sensitive.py` (`FX-SEC-001`) |
| Supply Chain | Scorecard + dependency-review + SBOM + pinned actions. | supply-chain gates |
| Excessive Agency | Connectors cannot write canonical state, approve signoff, or resolve compliance — emit-only to gateway. | authority boundary |
| Insufficient Logging | Hash-chained ledger + FEATURE_INDEX verified each PR. | `governance-gate.yml` |

**Operator-owned (gateway, not this repo):** prompt-injection canary on inbound
free-text, rate limiting, and the ingest hard-gate enforcement live in
`bicameral-mcp`/`bicameral-bot` (see the security-governance research brief
CRIT-1/CRIT-2).
