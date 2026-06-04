# AGT as a sidecar for `bicameral-bot` — evaluation & recommendation

**Status:** spike / recommendation (no cross-repo changes). 2026-06-04.
**Subject:** `microsoft/agent-governance-toolkit` (AGT) as a governance sidecar for `bicameral-bot`.

## What AGT is (consumable surface)

AGT (MIT, Python, ~35 MB, actively maintained — pushed 2026-06-04, "Policy enforcement, zero-trust identity, execution sandboxing, reliability engineering for autonomous AI agents; covers 10/10 OWASP Agentic Top 10"). The relevant consumable pieces:

- **`agent-governance-gate.yml`** — a **reusable `workflow_call`** with inputs `policy` (a policy YAML path), `agent manifest` path, and `python_version`. It runs `scripts/governance_gate.py` → policy validation + **Ed25519 signed deployment receipts** + a JSONL audit-log artifact; `require_receipt` can force-fail. This is exactly the sidecar entry point.
- A **policy engine** (`policy-engine-ci.yml`, `policy-validation.yml`) + the OWASP Agentic compliance mapping (`docs/compliance/owasp-agentic-top10-architecture.md`).

## Why `bicameral-bot` specifically

The bot is the Rust **gateway / governance core** — the agentic authority-enforcement surface. The cross-repo security brief (`SG-2026-06-03-H`) found the bot's authority boundary is **doctrine-only, not code-enforced** (review/dashboard routes accept canonical mutations with no actor identity — CRIT-2). AGT's **policy enforcement + zero-trust identity + execution sandboxing** target precisely that class of gap. The bot is where agentic-authority controls earn their keep, so it's the right (and only) repo in the ecosystem where AGT's agentic-specific machinery is clearly worth its weight.

## Integration model: CI sidecar, not in-process

- The bot is **Rust**; AGT is **Python**. Integration is a **CI sidecar / reusable-workflow**, not a code dependency: the bot's CI calls `uses: microsoft/agent-governance-toolkit/.github/workflows/agent-governance-gate.yml@<PINNED_SHA>` with a bot-authored policy YAML + agent manifest, running **alongside** the bot's native Rust gates (`clippy -D warnings`, `cargo-audit`) and our portable governance-integrity gate.
- No Rust↔Python linking; AGT runs in its own job and emits receipts/audit artifacts.

## Overlap vs. complementarity with our gates

| Concern | Our portable gates (this repo) | AGT |
|---|---|---|
| Ledger/feature-index integrity | ✅ governance-integrity gate | — |
| SAST / supply-chain / SBOM | ✅ | partial (also has these) |
| **Agent policy enforcement** | ❌ | ✅ policy engine |
| **Zero-trust identity / signed receipts** | ❌ (we hash-chain; no Ed25519 receipts) | ✅ Ed25519 deployment receipts |
| **Execution sandboxing** | ❌ | ✅ |
| **OWASP Agentic Top 10** | partial (mapping doc) | ✅ deterministic controls, 10/10 |

**Verdict: complementary, not redundant.** AGT adds the agentic-runtime + policy + signed-provenance layer the bot needs; our gates add the ledger-integrity + ecosystem-consistent CI layer. Run both; don't let AGT's secret/dep scanners duplicate ours (pick one per concern to avoid double-gating noise).

## Risks / caveats

- **Pin a SHA** — AGT is evolving fast (pushed today); a floating `@main` is a supply-chain hole.
- **Surface/size** — ~35 MB Python toolkit; consume only the `agent-governance-gate` reusable + policy engine, not the whole repo.
- **Policy-model fit** — AGT's policy/agent-manifest schema must be mapped to the bot's authority model; this is the real work of the spike, not the wiring.
- **Don't double-gate** — disable AGT's overlapping secret/dep scanners in favor of the ones already standardized across the ecosystem (TruffleHog + our supply-chain gates), or vice-versa, but not both.
- **Provenance reconciliation** — AGT's Ed25519 receipts and our hash-chained META_LEDGER are two provenance mechanisms; decide which is authoritative for the bot (recommend: ledger for governance history, AGT receipts for deployment attestation).

## Recommendation

**PROCEED with a bounded spike, in `bicameral-bot`, as its own governed cycle (separate repo, separate authorization).** Scope:
1. Add the bot's portable gates by consuming this repo's `_reusable-*.yml` (governance-integrity + supply-chain) — see `consuming-gates.md`.
2. Add AGT's `agent-governance-gate` reusable as a **CI sidecar** (SHA-pinned), authoring a minimal bot policy YAML + agent manifest mapped to the bot's authority routes (the CRIT-2 surface).
3. Output of the spike = a working bot CI that enforces both layers, plus a decision on provenance authority (ledger vs AGT receipts).

**Do NOT:** adopt AGT in-process, vendor the whole toolkit, or duplicate scanners. This is a CI/policy sidecar evaluation — the bot remains Rust and owns its authority logic; AGT enforces policy around it.

> No changes were made to `bicameral-bot` or AGT by this evaluation. Tracked as BACKLOG B3.
