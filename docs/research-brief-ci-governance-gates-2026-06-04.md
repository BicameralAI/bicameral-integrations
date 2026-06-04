# Research Brief

**Date**: 2026-06-04
**Analyst**: The Qor-logic Analyst
**Target**: CI gate ecosystem for `bicameral-integrations`, benchmarked against `microsoft/agent-governance-toolkit` (AGT), to cover security, OWASP, supply chain, code quality/consistency, and the compliance-evidence story (NIST AI RMF & SSDF, EU AI Act, SOC 2; GDPR/HIPAA applicability).
**Scope**: Which gates are genuinely enforceable in CI for a Python/stdlib-runtime repo, which "compliance" items are controls+mappings+evidence rather than scanners, and the exact action pins to mirror AGT's supply-chain hygiene. Source: AGT `.github/workflows/*` (read live via GitHub API, pushed 2026-06-04) + AGT README + our current CI.

---

## Executive Summary

AGT (public, actively maintained, "Covers 10/10 OWASP Agentic Top 10") runs ~40 workflows. The decisive finding for us: **AGT has no per-law `gdpr.yml`/`hipaa.yml`/`soc2.yml`/`nist.yml` "checkers."** Compliance is carried by three things — (1) **real automated scanners** (CodeQL, Scorecard, dependency-review, SBOM, secret-scanning, supply-chain pinning), (2) a **governance gate** (`scripts/governance_gate.py` → policy validation + Ed25519 provenance receipts + JSONL audit log) that is *blocking*, and (3) **`docs/compliance/` mapping docs** (`owasp-agentic-top10-architecture.md`, `nist-ai-rmf-alignment.md`, `soc2-mapping.md`) plus a tamper-evident **Merkle audit trail**. Its OWASP workflow is an *advisory* weekly AI-issue, not a build gate; its blocking quality gates are concrete shell checks (no-stubs, no-custom-crypto, security-audit-required); actions are **SHA-pinned**. **Our repo already owns the hardest compliance asset AGT builds from scratch — the QOR hash-chained META_LEDGER + `ai_provenance` manifests (EU AI Act Art. 13/14/50, AI RMF, SSDF tags).** So our gap is the *automated-scanner layer* + a CI-runnable *governance-integrity gate over the committed ledger* + the *compliance-mapping docs*. No blocking gaps → proceed to `/qor-plan` at L3.

## Findings

### F1 — Enforceable, always-relevant automated gates (adopt; map to OWASP + supply chain)
- **CodeQL** (`codeql.yml`): SAST, `push`+`pr`+weekly, `security-events: write`. Pins: `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2`, `github/codeql-action/{init,autobuild,analyze}@87557b9c84dde89fdd9b10e88954ac2f4248e463 # v4`. For us: `language: [python]` only.
- **OpenSSF Scorecard** (`scorecard.yml`): supply-chain posture, push-to-main + weekly, SARIF to code-scanning. Pins: `ossf/scorecard-action@4eaacf0543bb3f2c246792bd56e8cdeffafb205a # v2.4.3`, `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1`, `github/codeql-action/upload-sarif@8755…463 # v4`.
- **Dependency review** (`dependency-review.yml`): PR-gating, `fail-on-severity: moderate`, `comment-summary-in-pr: always`, license allowlist (MIT/Apache-2.0/BSD/ISC/PSF/0BSD/MPL-2.0/…). `actions/dependency-review-action # v5`.
- **SBOM** (`sbom.yml`): release-triggered, Anchore `anchore/sbom-action@e22c389904149dbc22b58101806040fa8d37a610 # v0.24.0` → SPDX + CycloneDX, attested via `actions/attest-sbom@c604332985a26aa8cf1bdc465b92731239ec6b9e # v4.1.0` + `actions/attest-build-provenance@a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32 # v4.1.0`.
- **Secret scanning**: we already run TruffleHog (`secret-scan.yml`) — keep; matches the mcp standard (SG-2026-06-03-H).
- **Supply-chain pinning** (`supply-chain-check.yml`): rejects unpinned dep ranges + requires lockfiles on dep-file PRs; all `uses:` are full-SHA pinned (a Scorecard "Pinned-Dependencies" criterion).
- **Python SAST/vuln** (not in AGT's Python set but always-relevant for us): **Bandit** (Python SAST → OWASP) + **pip-audit** (dependency CVEs). Our runtime is stdlib-only; dev deps are ruff/mypy/pytest — still scan.

### F2 — Code quality / consistency gates
- AGT `quality-gates.yml` (blocking, PR): custom shell checks (no-stubs, no-custom-crypto, security-audit-required, no-unauthed-registration, vendored-patch-audit) — security/design-pattern enforcement, NOT lint/type/coverage. Our lint/type/test gate already exists (`ci.yml`, ruff/mypy/pytest — widened to `adapter connectors` in PR #4).
- AGT also runs: `license-headers.yml` (blocking, `scripts/check_license_headers.py` over changed `.py/.ts/.cs/.rs/.go`), `license-check.yml`, `spell-check.yml`, `docs-quality.yml`, `pr-title-check.yml`, `pr-size.yml`, `dco.yml`, `workflow-lint.yml`, `auto-merge-dependabot.yml`. These are the "consistency / ecosystem-guideline" layer.

### F3 — Compliance is controls + mappings + evidence, NOT a per-law CI check
- AGT README "Standards Compliance" table maps **OWASP Agentic Top 10** (`docs/compliance/owasp-agentic-top10-architecture.md`), **NIST AI RMF 1.0** (full GOVERN/MAP/MEASURE/MANAGE, `nist-ai-rmf-alignment.md`), **EU AI Act** (`docs/compliance/`, "automated evidence"), **SOC 2** (`soc2-mapping.md`, "control mapping with audit-trail export"). **GDPR, HIPAA, NIST SSDF, ISO 27001 are not in AGT** — they live (if at all) in extended docs.
- The blocking `agent-governance-gate.yml` is a reusable workflow running `scripts/governance_gate.py` (stdlib-ish: `pyyaml`+`cryptography`) → policy validation + Ed25519 provenance receipt + 90-day audit-log artifact; `require_receipt` can force failure.
- **Mapping to us:** our QOR governance already emits the evidence AGT's gate produces — hash-chained `META_LEDGER`, `ai_provenance` manifests citing EU AI Act Art. 13/14/50 + AI RMF + SSDF tags, FEATURE_INDEX TDD verification. The CI-runnable analog is a **governance-integrity gate over the committed ledger** (the `.qor/` gate JSONs are gitignored, so CI verifies the *committed* chain): recompute each entry's `chain_hash = SHA256(content_hash + previous_hash)` and assert `previous_hash` links to the prior entry's chain hash; verify FEATURE_INDEX rows point at existing tests. Must be **stdlib-only** so it runs without the `qor` venv.

### F4 — Honest framework→control placement for our repo
- **OWASP** (web Top-10 relevant subset + agentic): input validation + no-canonical-write authority boundary (parse surfaces), fail-closed webhook signature verification (SG-2026-06-04-B), producer sensitive-data screen (`FX-SEC-001`), secret scanning, CodeQL/Bandit. Real + enforced.
- **NIST AI RMF + SSDF**: QOR phases (research/plan/audit/implement/substantiate) = MAP/MEASURE/MANAGE + SSDF PW/PS practices; provenance manifests carry the tags. Mapping doc + governance-integrity gate.
- **EU AI Act**: Art. 13/50 transparency + Art. 14 human-oversight + Art. 9 risk management = `ai_provenance` (`human_oversight` PASS/VETO/ABSENT) + plan `impact_assessment`. Mapping doc.
- **SOC 2**: Security/Confidentiality/Processing-Integrity/Change-Management = TruffleHog+CodeQL (security), sensitive screen (confidentiality), gated cycles + branch protection + hash-chained ledger (change mgmt + processing integrity, with audit-trail export). Mapping doc.
- **GDPR / HIPAA**: applicability + data-protection control mapping — the `FX-SEC-001` sensitive-data screen (rejects secrets/PHI/PAN), data minimization (connectors emit only evidence excerpts, never canonical state), purpose limitation (read-only → gateway). Mapping doc, framed as control alignment, NOT certification.

### F5 — Ecosystem portability (re: operator's cross-repo note)
The governance-integrity gate + `docs/compliance/` mappings + the scanner workflows are **repo-agnostic** (the ledger-verifier reads any `META_LEDGER.md`; the scanners are language-generic with a Python profile). They are the natural template to roll across `bicameral-bot` (Rust), `bicameral-mcp` (Python), `bicameral-cloud`. AGT itself could run as a **sidecar/reusable-workflow** for `bicameral-bot`'s agentic surface. (Cross-repo rollout is its own program — out of scope for this cycle; flagged for a follow-on.)

## Blueprint Alignment

| Blueprint claim | Finding | Status |
|---|---|---|
| Secret scanning + branch protection (ARCHITECTURE_PLAN governance controls) | TruffleHog present; gates extend it | MATCH |
| FEATURE_INDEX TDD obligation; ledger hash chain | governance-integrity gate enforces both in CI | MATCH |
| Producer is non-authoritative; sensitive screen is the PII/PHI guard | underpins OWASP/GDPR/HIPAA/SOC2 mappings | MATCH |
| stdlib-only runtime | governance gate + Bandit/pip-audit add no runtime deps (CI-only tools) | MATCH |

No DRIFT.

## Recommendations

1. **[P1] Proceed to `/qor-plan` at L3.** Add the full enforceable gate set + a stdlib governance-integrity gate + `docs/compliance/` mappings. Mirror AGT's SHA pins (above).
2. **[P1] Additive only** — new workflow files; do NOT edit `ci.yml` (pending PR #4 owns it). New branch off `main`.
3. **[P2] Posture phasing** — security-critical gates (CodeQL, Bandit, pip-audit, dependency-review, governance-integrity, secret-scan) **block** PRs; posture/coverage gates (Scorecard, SBOM, spell/docs) are **advisory/scheduled** so a new repo isn't wedged on bootstrap noise (matches AGT: OWASP-agent advisory, quality-gates blocking).
4. **[P2] Keep the governance gate stdlib-only** so it runs without the `qor` venv.
5. **[P3] Design for ecosystem reuse** (operator note) — the governance-integrity gate + compliance docs are portable to bot/mcp/cloud; AGT as a sidecar for `bicameral-bot` is a viable follow-on program (separate cycle).

## Updated Knowledge

SHADOW_GENOME **SG-2026-06-04-C**: compliance frameworks (GDPR/HIPAA/SOC2/NIST/EU AI Act) are NOT single CI checks — even Microsoft's AGT maps them via `docs/compliance/` + a governance gate + a tamper-evident audit trail. The enforceable CI layer is SAST/secret/dep/supply-chain/SBOM/Scorecard + a governance-integrity gate; the frameworks are control mappings that *cite* those gates + the QOR ledger/provenance as evidence. Never ship a `<law>.yml` that "passes" without verifying a real control.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
