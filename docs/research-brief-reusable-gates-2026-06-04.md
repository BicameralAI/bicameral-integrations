# Research Brief

**Date**: 2026-06-04
**Analyst**: The Qor-logic Analyst
**Target**: Factor the portable CI gates into **reusable workflows** (`workflow_call`) so the four-repo ecosystem (bot/mcp/cloud + this repo) consumes one source.
**Scope**: Which gates are portable, GitHub reusable-workflow mechanics, the cross-repo governance-script fetch, and the supply-chain posture for consumers. Builds on the `ci-gates-2026-06-04` cycle (Entry #21).

---

## Executive Summary

The gates from Entry #21 split cleanly into **portable** (repo-agnostic) and **language-specific** (parameterizable). GitHub reusable workflows (`on: workflow_call` + `inputs`/`secrets`, called via `uses: owner/repo/.github/workflows/file.yml@ref`) are the right mechanism. One real design point: `scripts/governance_gate.py` currently derives the repo root from `__file__`; for a reusable workflow that checks the script out of THIS repo to verify the **caller's** ledger, the script must accept a `--repo-root` argument. With that, every repo gets the governance-integrity gate + supply-chain gates from one pinned source. No blockers → `/qor-plan` at L2.

## Findings

### F1 — Portable vs language-specific
- **Portable (reusable as-is):** governance-integrity gate, dependency-review, OpenSSF Scorecard, SBOM, secret-scan (TruffleHog), PR-title hygiene, workflow-YAML lint. Repo-agnostic.
- **Language-specific (parameterize via inputs):** CodeQL (`languages` input — `python` here, `python,javascript` / `actions` / Rust-via-`go`? CodeQL supports python/js/java/csharp/cpp/go/ruby/swift/actions; Rust is not CodeQL-native → bot uses `clippy` instead), Bandit/pip-audit/ruff/mypy/pytest (Python-only).

### F2 — Reusable-workflow mechanics
- A reusable workflow declares `on: workflow_call` with typed `inputs:` (e.g. `languages`, `python-version`, `tooling-ref`) and optional `secrets:`. Callers reference it by path + ref: `uses: BicameralAI/bicameral-integrations/.github/workflows/_reusable-governance-gate.yml@<sha|tag>`.
- The reusable workflow executes in the **caller's** repository context (caller's `GITHUB_WORKSPACE`, checkout gets the caller's code).
- **Consumer supply-chain:** consumers should pin `@<sha>` (or a release tag) — same SHA-pin discipline as actions. Document this.

### F3 — Cross-repo governance-script fetch (the real design point)
- The governance-integrity gate needs `scripts/governance_gate.py`, which lives in THIS repo. A consumer repo doesn't have it. The reusable workflow therefore does a second `actions/checkout` (`repository: BicameralAI/bicameral-integrations`, `path: .governance-tooling`, `ref: <tooling-ref>` SHA-pinned) to fetch the script, then runs it against the **caller's** checked-out tree.
- **Required change:** `governance_gate.py main()` currently uses `Path(__file__).resolve().parents[1]` as repo root — wrong when the script is run from `.governance-tooling/`. Add `--repo-root` (default: parents[1]) so the reusable workflow passes the caller's `GITHUB_WORKSPACE`. Keep a `--ledger`/`--feature-index` override too. Backwards-compatible (this repo's own caller passes `.`).

### F4 — This repo becomes a consumer of its own reusable workflows
- The standalone gate workflows from Entry #21 become **thin callers** (`uses: ./.github/workflows/_reusable-*.yml`) — a local path reference (no ref needed for same-repo). This proves the reusable workflows work and avoids drift between "what we run" and "what we publish."

### F5 — Ecosystem fit (BACKLOG B3)
- `bicameral-mcp` (Python): consume governance-gate + security + supply-chain reusables, `languages: python`. Near-direct.
- `bicameral-bot` (Rust): consume governance-gate + dependency-review + scorecard + sbom + secret-scan + pr-hygiene reusables; SAST via its own `clippy`/CodeQL-unavailable-for-Rust path (cargo-audit). The governance-gate reusable works unchanged (it verifies a META_LEDGER, language-agnostic).
- `bicameral-cloud`: profile per stack.

## Blueprint Alignment

| Claim | Finding | Status |
|---|---|---|
| Gates are repo-portable (Entry #18 F5; SG-2026-06-04-C) | confirmed; reusable-workflow is the mechanism | MATCH |
| Governance gate is stdlib + verifies a committed ledger | works cross-repo with `--repo-root` | MATCH (1 small change) |
| Supply-chain: SHA-pin everything | consumers pin the reusable-workflow ref | MATCH |

No DRIFT.

## Recommendations

1. **[P1] `/qor-plan` at L2.** Create `_reusable-*.yml` for the portable gates + a parameterized `_reusable-codeql.yml`; convert this repo's gate workflows to thin callers; add `--repo-root` to `governance_gate.py` (+ test); write `docs/ecosystem/consuming-gates.md`.
2. **[P1] Pin discipline for consumers** — document `@<sha>` pinning of the reusable-workflow ref.
3. **[P2] Keep language-specific gates out of the shared layer** (Bandit/ruff/mypy belong to Python repos; bot uses clippy/cargo-audit).

## Updated Knowledge

SHADOW_GENOME **SG-2026-06-04-E**: a reusable governance-gate workflow that lives in repo A but verifies repo B's ledger must (a) checkout repo A's script to a side path (SHA-pinned) and (b) pass the caller's workspace as `--repo-root` — a script that derives its root from `__file__` will verify the *tooling* checkout, not the caller. Parameterize repo-root in any cross-repo verifier.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
