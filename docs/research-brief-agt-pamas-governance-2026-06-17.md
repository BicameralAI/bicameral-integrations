# Research Brief — AGT & PAMAS governance lessons (bicameral-integrations-owned re-scope)

**Date**: 2026-06-17
**Analyst**: The Qor-logic Analyst
**Target**: (1) `github.com/microsoft/agent-governance-toolkit` (AGT); (2) local paper `Proportional_Adaptive_Mutation_Authority_..._v2_Framework_Aligned.md` (PAMAS).
**Scope**: This is the **bicameral-integrations-owned** re-scope of the research originally recorded at META_LEDGER **#206**. It keeps only the conclusions this repo owns; the bicameral-mcp #148-specific findings are carried in **Appendix A as a handoff**, not as an owning record (see ADR-0018).
**Status**: Re-scope of #206 (ledger #207). The detailed AGT/PAMAS findings remain in the frozen #206 artifact `docs/research-brief-148-decision-capture-governance-2026-06-17.md`; this brief does not restate them, it re-homes the conclusions.

---

## Why this brief exists (provenance correction)

The original research was run in this repo but framed "in service of bicameral-mcp #148," and its owning
record (#206) was written into **this** repo's chain. That split a single decision across two tamper-evident
chains. Per **ADR-0018 (in-repo decision provenance)**, the owning record for a #148 decision belongs in
**bicameral-mcp**; this repo keeps the integrations-owned conclusions plus a labelled handoff. #206 stays
sealed and unmodified as the truthful record that the original was mis-scoped; this brief + #207 are the
append-only correction.

---

## Integrations-owned conclusions

These are the findings that govern **bicameral-integrations** itself (not #148):

1. **META_LEDGER tamper-evidence has external convergent validation (AGT ADR-0017).** Microsoft's audit
   system independently arrived at a SHA-256 Merkle/hash chain (`previous_hash` + `entry_hash`, self-contained
   `verify_chain()`, sub-ms overhead) — the same shape as our ledger. This is reassurance, not action.
2. **Known gap, already on our roadmap: full-chain replacement.** AGT ADR-0017 explicitly notes a hash chain
   proves *internal* integrity but does **not** resist wholesale chain replacement without **external
   anchoring**. Our ledger inherits this. It is already tracked as the [[release-trust-posture]] cosign/minisign
   + attestation milestone (bot #73). Cross-reference, do not re-derive.
3. **Deterministic-gate discipline confirms our advisory-mod posture (AGT ADR-0004).** AGT keeps LLMs out of
   the allow/deny loop; reasoning is confined to drafting and shadow-review. Our mods are already *advisory*
   (no direct signoff/blocking authority, ADR-0007/0013) — this is the same principle and reinforces that mods
   must never become enforcement gates.
4. **PAMAS taxonomy is a candidate frame for mod/connector authority.** PAMAS's orthogonal axes — target class
   M0–M5 × strength (Observed→Canonical) × downstream authority A0–A5, with fail-closed defaults and a
   validation≠authorization two-key — map cleanly onto our connector-readiness ladder (ADR-0012) and the
   evidence-adapter-not-state-authority boundary (ADR-0008). Worth evaluating if we ever formalize mod
   promotion. Advisory note only; no action this cycle.
5. **AGT-sidecar evaluation (BACKLOG B3) is well-founded.** AGT is a real, mature, multi-language governance
   platform (OWASP-Agentic/NIST-RMF/EU-AI-Act aligned, 32 indexed ADRs, RFC process). The [[ecosystem-governance-rollout]]
   plan to evaluate it as a bicameral-bot sidecar (B3) is sound; this brief upgrades B3 from speculative to
   evidence-backed.
6. **New governance rule adopted: in-repo decision provenance (ADR-0018).** The act of producing #206 surfaced
   the cross-repo ledger leak; the rule and its gate check are this cycle's primary integrations-owned output.

## Blueprint Alignment (integrations scope)

| Claim under review | Finding | Status |
|---|---|---|
| META_LEDGER hash chain is sufficient tamper-evidence | Internal integrity ✓; full-chain-replacement gap (AGT ADR-0017) → needs external anchoring | MATCH w/ caveat → [[release-trust-posture]] |
| Mods must stay advisory, never enforcement gates | AGT ADR-0004 (LLM out of allow/deny) confirms; matches ADR-0007/0013 | MATCH |
| Cross-repo dev cycles were harming ledger coherence | #206 split #148 provenance across two chains | DRIFT → corrected by ADR-0018 + gate check |
| AGT-sidecar eval (B3) is worth doing | AGT is mature + standards-aligned | MATCH (B3 upgraded to evidence-backed) |

## Recommendations (integrations)

1. **(done this cycle)** Adopt ADR-0018 + `governance_gate.py` subject-locality check.
2. **(P3)** When the release-trust milestone (bot #73) reaches cosign/attestation, explicitly cite AGT ADR-0017
   as the external-anchoring rationale.
3. **(P3, defer)** If mod-promotion is ever formalized, evaluate the PAMAS M/strength/A taxonomy as the schema.
4. **(handoff)** Carry Appendix A into a **bicameral-mcp** dev cycle to seal #148 there.

---

## Appendix A — Handoff to bicameral-mcp #148 (NOT an owning record)

> Reproduced here only as a transmittal. The owning record for these findings must be committed in a
> **bicameral-mcp** dev cycle (its ledger / a docs PR like the existing #536), per ADR-0018. Do not treat
> this appendix as #148's governance record.

**Core lesson for #148 (capturing implicit agent-authored decisions):** decision capture must be **passive and
reconstructive, not cooperative**.

- **AGT ADR-0018 (Reconstructible Decision BOM)** is the reference mechanism: reconstruct a decision's context
  after the fact from passive signals (audit / trust / policy / OTel traces); agents never cooperate; partial
  reconstruction is surfaced via explicit *completeness levels*; zero hot-path overhead. This validates #148's
  passive Phase-1 design and says the voluntary `bicameral.note_choice` tool (Phase 2) must be backstopped by
  passive reconstruction.
- **AGT ADR-0004**: an "is-this-a-decision?" LLM classifier may only be an **advisory candidate generator**,
  never a gate.
- **AGT shadow mode + ADR-0030 (action-bound, fail-closed approval)**: ship #148 signals **observe-only first**,
  measure FP rate against a labelled corpus before any signal writes the ledger; reuse **one** action-bound
  capture contract across #147 (developer-stated) and #148 (agent-implicit) — origin is a field, not a fork.
- **PAMAS decision-tree shape**: not a single tree but a **multi-axis classification lattice** (target M0–M5 ×
  strength Observed→Canonical × downstream authority A0–A5) → two-evaluator pipeline (lifecycle then authority)
  → 5 handling lanes. Strengths: confidence-vs-consequence separation, fail-closed defaults, first-class
  demotion, validation≠authorization. **DRIFT for #148:** the flow presumes a *declared* Mutation Contract
  ("agent proposes mutation") and so **starts one step too late** — no upstream *detection* stage for the
  *undeclared* decisions that are #148's entire population.
- **Synthesis for #148:** PAMAS taxonomy as the capture **schema** + AGT ADR-0018 reconstruction as the capture
  **mechanism** + an advisory LLM detector shipped **shadow-first**. Tag captures `agent_origin="implicit_choice"`
  vs `developer_stated` with the richer M/strength/A axes rather than a flat flag.

_Detailed findings + citations: see the frozen #206 artifact `docs/research-brief-148-decision-capture-governance-2026-06-17.md`._

---

_Research re-scoped. Findings are advisory — the selection of which #148 signal(s) to greenlight, and the sealing of that decision in bicameral-mcp, remains with the Governor._
