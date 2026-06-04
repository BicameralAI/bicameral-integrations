# Consuming the Bicameral governance gates

The portable CI gates live as **reusable workflows** in
`bicameral-integrations/.github/workflows/_reusable-*.yml`. Other repos in the
ecosystem (`bicameral-bot`, `bicameral-mcp`, `bicameral-cloud`) consume them by
reference, so there is one source of truth for the gate logic.

## Portable vs language-specific

| Reusable | Portable? | Notes |
|----------|-----------|-------|
| `_reusable-governance-gate.yml` | ✅ any repo with a hash-chained `META_LEDGER` + `FEATURE_INDEX` | language-agnostic |
| `_reusable-dependency-review.yml` | ✅ | GitHub-native |
| `_reusable-scorecard.yml` | ✅ | OpenSSF posture |
| `_reusable-sbom.yml` | ✅ | Anchore SPDX + optional attest |
| `_reusable-pr-hygiene.yml` | ✅ | conventional PR title |
| `_reusable-codeql.yml` | ⚠️ parameterized | `languages` input; **CodeQL has no Rust** — `bicameral-bot` uses `clippy` + `cargo-audit` instead |
| Bandit / pip-audit / ruff / mypy / pytest | ❌ Python-only | keep local in Python repos |

## How to consume (SHA-pin everything)

```yaml
# .github/workflows/governance-gate.yml in a consumer repo
name: Governance Gate
on:
  pull_request: { branches: ["main"] }
  push: { branches: ["main"] }
permissions:
  contents: read
jobs:
  governance:
    uses: BicameralAI/bicameral-integrations/.github/workflows/_reusable-governance-gate.yml@<PINNED_SHA>
    with:
      tooling-ref: <PINNED_SHA>   # SHA of bicameral-integrations to fetch the verifier from
```

```yaml
# CodeQL for a Python consumer
jobs:
  codeql:
    uses: BicameralAI/bicameral-integrations/.github/workflows/_reusable-codeql.yml@<PINNED_SHA>
    with:
      languages: python
```

**Pin discipline:** pin both the `uses: …@<sha>` ref **and** the
`tooling-ref` input to a commit SHA — a floating `@main` is a supply-chain hole
(a malicious or accidental change to the reusable would run in your repo).

## The `--repo-root` contract (why the governance gate works cross-repo)

`scripts/governance_gate.py` accepts `--repo-root` (default: its own repo). The
reusable workflow checks the script out of `bicameral-integrations` to a side
path (`.governance-tooling`) and runs it with
`--repo-root "$GITHUB_WORKSPACE"` — i.e. against the **consumer's** checked-out
tree, verifying the *consumer's* `META_LEDGER` + `FEATURE_INDEX`, not the
tooling repo's (SG-2026-06-04-E). A consumer repo only needs a hash-chained
`docs/META_LEDGER.md` and a `docs/FEATURE_INDEX.md` in the same format.

## Per-repo adoption notes

- **`bicameral-mcp` (Python):** consume governance-gate + dependency-review +
  scorecard + sbom + pr-hygiene + `_reusable-codeql` (`languages: python`); keep
  Bandit/ruff/mypy/pytest local.
- **`bicameral-bot` (Rust):** consume governance-gate + dependency-review +
  scorecard + sbom + pr-hygiene; SAST via `clippy -D warnings` + `cargo-audit`
  (CodeQL has no Rust analyzer). See BACKLOG B3 (AGT sidecar evaluation).
- **`bicameral-cloud`:** profile per stack; the governance-gate + supply-chain
  reusables are stack-agnostic.
