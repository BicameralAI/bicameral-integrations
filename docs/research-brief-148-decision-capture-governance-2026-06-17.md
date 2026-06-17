# Research Brief — Decision Visibility & Governance Shape for Implicit Agent-Authored Decisions

**Date**: 2026-06-17
**Analyst**: The Qor-logic Analyst
**Target**: (1) `github.com/microsoft/agent-governance-toolkit` (AGT) — visibility, governance, and decision processes; (2) local conceptual paper `Proportional_Adaptive_Mutation_Authority_Systems_Agnostic_Architecture_v2_Framework_Aligned.md` (PAMAS) — decision-tree shape.
**Scope**: Inputs to `BicameralAI/bicameral-mcp#148` (capturing implicit decisions the agent makes while implementing). Advisory only; no code or contract change in this repo.
**In service of**: bicameral-mcp #148 (OPEN; research delivered as that repo's PR #536; awaiting greenlight on which Phase-1 signal(s) to build).

---

## Executive Summary

Both targets converge on the same load-bearing lesson for #148: **decision capture must be passive and reconstructive, not cooperative**. Microsoft's AGT operationalizes this in production via **ADR-0018 (Reconstructible Decision BOM)** — it reconstructs a decision's full context *after the fact* from existing observability signals rather than asking the agent to report into a BOM builder, with explicit *completeness levels* when reconstruction is partial. The PAMAS paper supplies the complementary half: a rigorous **classification taxonomy and lifecycle** for *what* a captured decision is (target class M0–M5 × strength × downstream authority A0–A5), with fail-closed defaults. The critical drift to flag: PAMAS's decision flow is shaped as a **cooperative proposal lattice** (it presumes the agent emits a structured Mutation Contract) and therefore *starts one step too late* for #148, whose entire premise is decisions the agent never declares. The synthesis is to adopt PAMAS's taxonomy as the capture *schema* and AGT's reconstruction as the capture *mechanism*.

No drift was found against this repo's own governance model; both targets reinforce the bicameral hash-chained ledger and review-at-promotion-boundary posture.

---

## Findings

### A. Microsoft Agent Governance Toolkit (AGT) — visibility, governance, decision processes

AGT is a mature, multi-language (Python/.NET/TS), OWASP-Agentic-Top-10 / NIST-RMF / EU-AI-Act-aligned governance platform in public preview. It maintains a disciplined decision record: **32 indexed ADRs** (`docs/adr/`, with `index.md` + `README.md`), an `RFC_PROCESS.md`, `GOVERNANCE.md`, `CHARTER.md`, and a full compliance crosswalk set (`docs/compliance/`: OWASP ASI, NIST RMF, ISO-42001, EU-AI-Act checklist, SOC2, post-market-monitoring).

Key lessons of relevance to #148:

1. **Reconstructible Decision BOM over pre-built (ADR-0018)** — *the* central lesson.
   - `DecisionBOMBuilder` reconstructs a decision's context on demand by querying four protocol-based signal sources: `AuditSource`, `TrustSource`, `PolicySource`, `TraceSource` (OTel spans).
   - Design principles: **non-invasive** (no agent reporting, no coupling to the action pipeline), **protocol-based** (swappable sources), **completeness levels** (BOM reports whether reconstruction is full or partial — partial is *surfaced*, never silently incomplete), zero hot-path overhead.
   - Direct read for #148: the passive Phase-1 recommendation (commit-message + transcript prose scan) is the *right shape* — agents "never need to cooperate." A voluntary `bicameral.note_choice` tool (#148 Phase 2) is the cooperative analogue and must be backstopped by passive reconstruction, exactly as AGT keeps the BOM passive.
   - Citation: `docs/adr/0018-reconstructible-decision-bom-over-prebuilt.md`; impl `agent-mesh/.../governance/decision_bom.py`.

2. **Merkle / SHA-256 hash chain for audit tamper-evidence (ADR-0017)** — convergent-evolution validation of bicameral's `META_LEDGER`.
   - Each `AuditEntry` carries `previous_hash` + `entry_hash`; `MerkleAuditChain.verify_chain()`; detects modification, deletion, reordering; self-contained offline verification; sub-ms overhead; **no protection against full-chain replacement without external anchoring**.
   - Read for bicameral: the same limitation applies to `META_LEDGER` — the hash chain proves *internal* integrity but a wholesale replacement needs the external anchor (this is precisely the [[release-trust-posture]] cosign/minisign + attestations milestone). Citation: `docs/adr/0017-merkle-chain-for-audit-tamper-evidence.md`.

3. **Keep policy evaluation deterministic; LLM out of the allow/deny loop (ADR-0004)** — governs *where* model reasoning may live.
   - Enforcement-time decisions use declarative rules (Rego/Cedar); LLM reasoning is confined to *drafting policy* and *reviewing shadow-mode findings* — never the final allow/deny.
   - Read for #148: an LLM classifier asking "did this diff embody a design choice?" is legitimate **only as a candidate generator** (advisory), never as an authoritative gate. This matches #148's "candidate implicit decision" framing and bicameral's bicameral-review model. Citation: `docs/adr/0004-keep-policy-evaluation-deterministic.md`.

4. **Action-bound, fail-closed approval protocol (ADR-0030)** — `require_approval` is a *suspended* decision (not allow, not deny); an action digest binds the approval to the exact action; the runtime revalidates immediately before execution; replay/expiry are rejected; no LLM judge as authority; fail-closed on incomplete inputs. Read for the #147/#148 split: developer-stated vs agent-implicit decisions can share one durable, action-bound capture contract rather than divergent ad-hoc paths.

5. **Shadow mode** — AGT runs policies in observe-only before enforce, with humans reviewing open-text findings out of the enforcement path. Read for #148: Phase-1 signals should ship as **shadow/observe-only first**, measuring the false-positive rate against a labeled corpus before any signal is allowed to gate — directly satisfying #148's acceptance bar (≤1 spurious decision / 10 implementing turns).

6. **Process scaffolding as a product property** — AGT treats decisions as first-class, indexed, status-lifecycled artifacts (`Status: proposed|accepted`, `last_reviewed`, `owner`, related-issue links). This *is* bicameral's core value claim ("decisions are first-class artifacts"); AGT is a concrete reference implementation of operationalizing it at scale (CloudEvents export ADR-0021, OTel BatchSpanProcessor ADR-0019, append-only delta engine ADR-0023, data-provenance model `docs/compliance/data-provenance-model.md`).

### B. PAMAS local paper — decision-tree shape

The paper proposes *Proportional Adaptive Mutation Authority*: adaptation is broadly available, but authority to make a mutation durable/influential/shared/action-enabling rises **in proportion to consequence**. Review is applied "at promotion and consequence boundaries, not at every observation boundary" (§2).

**Shape characterization — it is not a single decision tree; it is a multi-axis classification lattice feeding a lifecycle state machine routed through handling lanes.**

- **Three orthogonal axes** (a captured decision is a tuple, not a path):
  - *Target class* M0–M5 (what is changed): M0 execution-local → M1 preference → M2 operational association → M3 reusable procedure/capability → M4 shared/identity-bearing fact → M5 governance/security/action authority (§7).
  - *Strength/lifecycle*: `Observed → Tentative → Reinforced → Promoted → Canonical`, with an explicit demotion branch `↘ Decaying → Archived/Deprecated/Blocked` (§8).
  - *Downstream authority* A0–A5 (max consequence it can influence): A0 retrieval-only → A5 governance change (§9). Explicitly: "strength and authority must be evaluated together" (§9.1) — the lattice is a *product* of axes.
- **Routing layer**: five handling lanes (Lane 1 transient-auto → Lane 5 restricted-authority) are the leaf actions (§10).
- **Control flow**: a pipeline with **two evaluators in series** — a *lifecycle evaluator* (recommends retain/reinforce/promote/decay/block) then an *authority evaluator* (auto / substantiated / review-required / veto) — then persist-with-lineage → monitor → feedback (§6, §15.3).
- **Decision record**: the structured *Adaptive Mutation Contract* (§12) — `proposal_id`, proposing agent + charter version, target {class, scope}, mutation {operation, strength delta, downstream_authority, reversibility}, basis {evidence_refs, validation_refs, correction_refs, confidence, freshness, sensitivity}, recommended_handling, policy_decision_ref.

**Strengths of the shape:**
- Orthogonal axes prevent the common error of conflating *confidence* with *consequence* (a low-confidence/high-consequence mutation is retained as an observation but blocked from influence).
- **Fail-closed defaults are the strongest branch rule**: an underspecified mutation must *not* be classified low-risk; "unknown consequence must not be converted into presumed safety" (§12.2); no auto-approval on missing classification (§16); no promotion on recurrence/retrieval/confidence alone — "a mistake repeated ten times … is merely an organized mistake" (§1.2, §14.1).
- **Demotion is a first-class reverse edge** (§8.1) — the structure has revocation/supersession, not just promotion.
- **Two-key separation**: validation (capability is trustworthy) is structurally separate from authorization (permission to use it autonomously) — "validation can justify trust in a capability; it does not automatically grant permission" (§9.1, §15.2).

**Gaps / drift relative to #148:**
- **Starts one step too late.** The flow's step 2 is "agent *proposes* mutation within its charter" (§6) — it presumes a declared proposal (the Mutation Contract). #148 targets *undeclared* decisions (picks `requests` over `httpx`, skips retries, swallows an exception) that never become a proposal. The lattice has no upstream *detection* stage. This is the key contrast with AGT's passive reconstruction and the reason a pure-PAMAS approach cannot satisfy #148 alone.
- **No concrete discriminator function.** The axes are qualitative; the paper (deliberately, being systems-agnostic) gives no operational threshold for M2-vs-M3 or Observed-vs-Tentative. #148's measurable FP/catch-rate acceptance bar requires operationalizing thresholds PAMAS leaves abstract.
- **Cooperative provenance assumption.** The Mutation Contract is pre-built at proposal time (evidence_refs supplied by the proposer); #148 has no proposer, so provenance must be *reconstructed* (AGT ADR-0018 model).

---

## Blueprint Alignment

| Claim under review | Actual finding | Status |
|---|---|---|
| #148 Phase-1 "passive capture, no agent cooperation" is the right architecture | AGT ADR-0018 ships exactly this (reconstructible, non-invasive, completeness-aware) in production | MATCH (strong external validation) |
| An LLM "is-this-a-decision?" classifier can gate decision capture | AGT ADR-0004 confines LLM reasoning to candidate-generation/shadow-review, never the gate | MATCH — use classifier as advisory candidate generator only |
| PAMAS provides a ready decision tree for #148 | PAMAS is a cooperative-proposal lattice; lacks the upstream *detection* stage #148 needs | DRIFT — taxonomy reusable, control-flow entry point is not |
| bicameral META_LEDGER hash chain is sufficient tamper-evidence | AGT ADR-0017 confirms internal integrity but flags full-chain-replacement gap (needs external anchoring) | MATCH with caveat → reinforces [[release-trust-posture]] cosign/attestation milestone |
| Repo governance health is sound | `governance_gate.py` re-derives #1..#205 clean; the qor-logic "canonical hash markup" lint on #123–205 is a known non-gating cross-tool mismatch | MATCH (no DAMAGED/INCOMPLETE) |

---

## Recommendations

1. **(P1) Adopt the reconstruction model for #148 capture mechanism.** Mirror AGT ADR-0018: reconstruct an implicit decision's context from passive signals (commit message, stream-json transcript, diff shape, OTel-equivalent tool-call trace) rather than relying on agent self-report. Carry an explicit *completeness level* on every candidate so partial captures are surfaced, not silently dropped.
2. **(P1) Adopt the PAMAS taxonomy as the capture schema, not the control flow.** Tag each captured implicit decision with `target_class` (M0–M5), `strength` (Observed→Canonical), and `downstream_authority` (A0–A5). This gives #148 a principled, consequence-proportional way to triage which implicit decisions warrant a ledger entry vs which decay — and distinguishes `agent_origin="implicit_choice"` from #147's `developer_stated` with a richer axis than a flat flag.
3. **(P1) Add the detection stage PAMAS omits.** Place an LLM classifier strictly as an *advisory candidate generator* (ADR-0004 discipline) on `PostToolUse(Edit|Write)` and on assistant prose; nothing it emits gates anything. Ship it **shadow/observe-only first** and measure FP rate against a labeled corpus before promoting to ledger writes — this is how AGT and #148's acceptance bar align.
4. **(P2) Carry the fail-closed default into capture.** A diff whose design intent cannot be reconstructed should be marked `unsubstantiated`/low-strength and visibly so — never silently presumed innocuous (PAMAS §12.2; §13.3 "do not fabricate proof").
5. **(P2) Reuse one action-bound decision contract** across #147 (developer-stated) and #148 (agent-implicit) rather than divergent paths (AGT ADR-0030 lesson); origin is a field, not a fork.
6. **(P3 / cross-repo) Note the chain-replacement gap.** AGT ADR-0017 confirms the bicameral ledger's hash chain needs external anchoring to resist wholesale replacement — already on the roadmap as [[release-trust-posture]] (cosign/minisign milestone C); cross-reference rather than re-derive.
7. **(housekeeping) Route the qor-logic ledger lint to /qor-remediate.** The #123–205 "canonical hash markup" mismatch is non-gating but recurs in every preflight; resolve the cross-tool format divergence once.

---

## Updated Knowledge

A Shadow-Genome lesson was recorded (SG-2026-06-17): *passive reconstruction beats cooperative self-report for decision capture* — proven by convergent evidence from AGT ADR-0018 (production) and the failure mode of PAMAS's proposal-first lattice for undeclared decisions. See `docs/SHADOW_GENOME.md`.

---

_Research complete. Findings are advisory — the selection of which #148 signal(s) to greenlight, and where the implementation issue lands, remains with the Governor._
