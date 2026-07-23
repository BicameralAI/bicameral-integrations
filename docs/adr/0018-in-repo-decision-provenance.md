# ADR-0018: In-repo decision provenance (governed writes land in the owning repo)

**Date:** 2026-06-17
**Status:** Accepted (operator decision 2026-06-17; supersedes the implicit cross-repo practice that produced META_LEDGER #206)
**Level:** L1 (governance process; no `src/` or connector-contract change)
**Relates to:** ADR-0011 (bicameral-review-bot — cross-repo authority split), ADR-0008 (integrations are evidence adapters, not state authorities)
**Grounded by:** META_LEDGER #206 (the leak), #207 (this decision); `docs/research-brief-agt-pamas-governance-2026-06-17.md`

## Context

`/qor-research` was run in **bicameral-integrations** but framed "in service of **bicameral-mcp #148**."
Its governed outputs — research brief, gate artifact, and **META_LEDGER #206** — were written into the
**bicameral-integrations** hash chain even though the decision they record is owned by **bicameral-mcp**
(whose #148 research already shipped as that repo's PR #536). The result was **split provenance**: one
decision recorded across two independent, tamper-evident chains, with neither chain holding the complete
record. An auditor reading the integrations chain finds a sealed entry that maps to no integrations code,
contract, or issue; an auditor reading bicameral-mcp finds #148 research that omits #206's findings.

This is the precise failure mode the ecosystem's own governance research warns against (AGT ADR-0018
"reconstructible decision BOM," and the PAMAS paper): a decision must be a **single, traceable, first-class
artifact**. Two homes is no home. The hash chain's value as audit evidence depends on every entry mapping
to something the owning repo actually governs.

The naive correction — "never operate across repos" — over-rotates. Research *cannot* be produced without
**reading** across repos (this brief read the Microsoft toolkit and bicameral-mcp #148). Banning reads would
either block legitimate work or, worse, push contributors to stop recording cross-repo learning. The defect
was never the read; it was the **governed write landing in the wrong chain**.

## Decision

1. **Cross-repo reads are always permitted.** A dev cycle may read any repo, issue, or external source it
   needs to do its work.
2. **Governed writes follow the owning repo.** Every tamper-evident or first-class governance artifact —
   META_LEDGER entry, ADR, local gate artifact, research brief that *is* the owning record,
   FEATURE_INDEX row — must be committed to the repo whose code, contract, or issue the decision governs.
   If research done in repo A is in service of repo B's decision, the owning record lands in **B**; A may
   keep at most a clearly-labelled **handoff** (a transmittal, not the owning record).
3. **A dev cycle is scoped to one repo's chain.** Do not append to repo A's META_LEDGER for work whose
   subject is repo B. Run the cycle in B, or hand off to a B cycle.
4. **Ecosystem-wide governance has one designated owner.** Genuinely cross-cutting governance (governing all
   Bicameral repos — see the ecosystem-governance rollout) is recorded once, in a single designated owner
   repo, never smeared into whichever repo the operator happens to be standing in.
5. **Enforcement.** `scripts/governance_gate.py` flags any META_LEDGER **entry header** that names a sibling
   Bicameral repo as its subject (`bicameral-mcp|bot|cli|core`). #206 is the single documented, allowlisted
   exception, corrected by #207. New violations fail the gate.

## Consequences

- Each repo's hash chain stays coherent: every entry maps to that repo's artifacts, so the chain remains
  meaningful audit evidence.
- A decision has exactly one owning chain; no split or duplicate provenance.
- The cost is a little more ceremony when research and ownership live in different repos (produce a handoff,
  then run/seal the owning cycle in the owning repo) — accepted as the price of single-source provenance.
- The gate check is header-scoped and low-false-positive (body mentions of other repos — e.g. "bot #405" —
  are reads/relations, not subject ownership, and are unaffected).
- #206 is **not** rewritten (sealed artifacts are never mutated); it stands as the truthful record that the
  original work was mis-scoped, with #207 as the append-only correction.

## References

- `scripts/governance_gate.py` (`verify_entry_subject_locality`)
- `docs/META_LEDGER.md` #206 (leak), #207 (correction + this decision)
- `docs/research-brief-agt-pamas-governance-2026-06-17.md` (integrations-owned re-scope + #148 handoff appendix)
- AGT ADR-0018 (reconstructible decision BOM) — external precedent that decisions are single first-class artifacts
