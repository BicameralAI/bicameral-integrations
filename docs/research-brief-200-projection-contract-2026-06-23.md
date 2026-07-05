# Research Brief — Target integration descriptors & projection profiles for governed egress (#200)

**Date**: 2026-06-23
**Analyst**: The Qor-logic Analyst
**Target**: RFQ #200 — the integrations-side model for governed **egress projection** targets (the egress mirror of #173/ADR-0017)
**Scope**: define `TargetIntegrationDescriptor` / `ProjectionProfile` / `TargetAdapter` + the first Linear projection family + the authority boundary; ground the ADR-0019 + consumable spec. **No code; no egress mechanics.**

---

## Executive Summary

#200 is the **egress counterpart** to the ingress/discovery RFQ #173 (answered by ADR-0017 +
`PROVIDER_ACQUISITION_CONTRACT.md`). It asks integrations to own the **target-specific projection
*shape*** — metadata describing what a target tool can render/create/comment/update and how a projection
maps to it — **without** owning the egress *mechanics*. The single load-bearing finding: this **refines**
(does not contradict) the existing rule that "egress execution lives in sidecar/sdk, not here"
(`CONNECTOR_AUTHORITY_LIMITS.md`). Integrations gains a **descriptor** (a `ProjectionProfile` is metadata,
the egress analogue of a `ProviderResourceDescriptor`); the bot/sidecar still owns policy, approval,
`EgressProjection`/`EgressReceipt`, and reconciliation interpretation. The same target-boundary docs serve
both directions ("same target docs, opposite direction"). The bot#528 attack surface (egress recreating
external truth drift) is answered structurally by **shape-only profiles + required canonical-ref +
required receipt + a forbidden-canonical-mutation rule**. 0 drift against the anchors; deliverable is
ADR-0019 (Proposed) + `docs/PROJECTION_CONTRACT.md`, awaiting cross-repo (bot#527/#528) sign-off.

## Findings

### F1 — Cross-repo owner decisions (OPEN) — bot#527 / bot#528

- **bot#527** ("RFQ: Governed egress projections for external execution surfaces", OPEN) is the bot-side
  counterpart; it places **target-specific egress shape in integrations** while the bot owns the governed
  execution. #200 is the integrations-side answer.
- **bot#528** ("Attack surface: Governed egress projections may recreate external truth drift", OPEN) is a
  security RFQ the ADR **must answer**: a projection that writes to an external tool, then reads that
  external state back as authoritative, would let external systems launder themselves into canonical
  Bicameral truth. The integrations-side mitigation is structural (F6).
- Status: both OPEN → ADR-0019 is **Proposed**, not Accepted (mirrors ADR-0017 awaiting bot#405).

### F2 — Authority anchors + the ownership refinement (the crux)

| Anchor | What it fixes |
|---|---|
| ADR-0008 (evidence adapters, not state authorities) | integrations never owns canonical state |
| `CONNECTOR_AUTHORITY_LIMITS.md` | *"Egress (propose-only writes) lives in `bicameral-sidecar`/`bicameral-sdk`, **not here**"* — egress **execution** is not in integrations |
| ADR-0011 (proposed-action / review bot) | mutations are *proposed*, governed + executed bot-side |
| ADR-0017 §4 | `create_provider_resource` is **not** on the discovery Protocol — a provider-safe create is a `ProposedAction`; the bot governs/executes. **Projection generalizes this.** |
| ADR-0015 (connector config descriptor) | the per-target, machine-readable config contract integrations already owns (precedent for a descriptor that integrations owns + a consumer renders/executes) |

**Refinement (not contradiction):** #200 adds an integrations-owned **shape descriptor** for egress —
`ProjectionProfile` (metadata: what the target can render/write, which fields, what receipt). Egress
**execution, policy, approval, eligibility, receipts, and reconciliation interpretation remain
bot/sidecar-owned**. The ownership sentence makes the line exact:

> *Integrations may describe what a target can read, render, or write. Bot decides whether Bicameral may
> project anything into that target.*

So `ProjectionProfile` is the egress analogue of `ProviderResourceDescriptor`: a **fact about target shape
+ capability**, never an authority object. It must not grant permission, waive approval, decide
eligibility, or create authority.

### F3 — Ingress contract to mirror + cross-reference

`docs/PROVIDER_ACQUISITION_CONTRACT.md` (+ ADR-0017) is the template: Status/Decision-record/Answers header
→ Boundary → object shapes (tables) → enums → operations → security → per-provider section → open/cross-repo.
The projection spec mirrors this **and shares the same per-target API truth**: a target's `api_docs_ref` /
`auth_scopes` / `target_surfaces` are declared **once** and consumed by both the connector (ingress) and
the projection (egress) profiles. This is the RFQ's "same target docs, opposite direction" and satisfies the
non-goal "do not create a new egress-only documentation universe."

### F4 — Linear target specifics (first projection family) — reuse the ingress side

The just-built Linear ingress side (`connectors/linear/`, `protocol/provider_acquisition/linear/`) already
fixes the shared target facts: GraphQL `https://api.linear.app/graphql`; auth = personal API key in the
**raw `Authorization` header (no Bearer)**; surfaces = issue, comment (workspace→team→project→issue). The
first projection family reuses these:

| Profile | Target surface | Operation | Notes |
|---|---|---|---|
| `linear.issue.summary.v1` | issue | create/update an issue **summary/description** | render a governed summary onto an issue |
| `linear.issue.work_item.v1` | issue | create an issue (**work item**) | a governed work item projected as a Linear issue |
| `linear.comment.status.v1` | comment | create a status **comment** on an issue | a governed status note as a comment |

Linear write scope: the personal API key's mutation capability (Linear `issueCreate`/`issueUpdate`/
`commentCreate` mutations) — **declared as capability, not exercised here** (no mutation behavior built —
RFQ non-goal).

### F5 — The unifying object: `TargetIntegrationDescriptor`

One per target system, unifying both directions under shared target facts:
`{target_system, api_docs_ref, auth_scopes, target_surfaces, ingress_capabilities, egress_capabilities,
connector_profiles, projection_profiles, target_adapters}`. The `connector_profiles` reference the existing
ingress connectors (#178 discovery + the active/passive/webhook modes); `projection_profiles` are the new
egress shapes; `target_adapters` declare per-target operation/rendering/credential/rate-limit/receipt-mapping
constraints. This is the "connectors and projections are opposite directions through the same target
boundary" model made concrete.

### F6 — bot#528 answer (structural, integrations-side)

External truth drift is prevented by **construction**, not policy:

1. **Shape-only profiles.** A `ProjectionProfile` carries no permission/approval/eligibility/authority —
   it cannot itself cause a write. (Same discipline as discovery descriptors being provider-facts-only.)
2. **`required_canonical_ref`.** Every projection must carry a back-reference to the canonical Bicameral
   decision it renders; the external artifact is a *rendering of* canonical truth, never a source of it.
3. **`required_receipt` + `receipt_mapping` (TargetAdapter).** The external write returns a **receipt**
   (id/url/status) that maps back to the bot; the bot interprets reconciliation. Integrations **never reads
   external state back as Bicameral authority** — `forbidden_fields` + the "external state interpreted as
   Bicameral authority" prohibition forbid it.
4. **`mutation_capability` is a declaration, not a grant.** It states what the target *can* do; the bot
   decides whether Bicameral *may* (approval, `EgressEligibilityCheck`, `ProjectionPolicy` — all bot-owned).
5. **No canonical truth model per target.** Profiles map *to* target shape; they never define a
   target-specific truth model (RFQ non-goal).

## Blueprint Alignment

| RFQ #200 claim | Finding | Status |
|---|---|---|
| ProjectionProfile is shape/capability metadata only — no permission/approval/eligibility/authority | F2/F6 | MATCH |
| Connectors + projections share one target-docs source | F3/F5 | MATCH |
| Bot owns policy/approval/EgressProjection/EgressReceipt/reconciliation | F1/F2 | MATCH |
| First Linear family reuses the ingress target facts | F4 | MATCH |
| Egress execution NOT in integrations (refined: shape descriptor in, execution out) | F2 (`CONNECTOR_AUTHORITY_LIMITS.md`) | MATCH (refines, with a one-line note added to the authority-limits doc) |

## Recommendations (for /qor-plan)

1. ADR-0019 (Proposed, L2) defines the three objects + the authority boundary + the bot#528 answer +
   cross-links ADR-0008/0011/0015/0017; mirrors ADR-0017's structure.
2. `docs/PROJECTION_CONTRACT.md` is the consumable spec (projection counterpart of
   `PROVIDER_ACQUISITION_CONTRACT.md`): duality model, object tables, allowed/forbidden lists, shared-docs
   model, the first Linear family. Cross-references the ingress contract; **no new doc universe**.
3. Add a one-line clarification to `CONNECTOR_AUTHORITY_LIMITS.md`: egress *execution* stays sidecar/sdk; the
   egress *shape descriptor* (`ProjectionProfile`) is integrations-owned, authority-free.
4. Identify follow-up issues: (a) bot-owned `EgressProjection`/`EgressReceipt`/`EgressEligibilityCheck`/
   `ProjectionPolicy` (bot#527/#528); (b) an integrations-side `projection-profile` descriptor schema +
   validator (the ADR-0015 analogue for projections) — a future build, NOT this RFQ.
5. **Strictly metadata/docs only** — no `EgressProjection`/receipt/Linear-mutation code (RFQ non-goals).

## Open Questions / risks

- **OQ1 (cross-repo)**: bot#527/#528 must confirm they consume `TargetIntegrationDescriptor`/
  `ProjectionProfile`/`TargetAdapter` in this shape (Proposed until sign-off; mirrors ADR-0017/#405).
- **OQ2 (schema timing)**: a machine-readable projection-profile schema (the ADR-0015 analogue) is a
  follow-up, not this RFQ — the ADR records the shape; the schema/validator land later.
- **OQ3 (ledger)**: this branch is off `dev` head #222; entries continue #223 (RESEARCH) → #224 (AUDIT) →
  #225 (IMPLEMENT). No fork.

## Updated Knowledge

The integrations↔bot boundary now has a **symmetric pair**: ingress = `ProviderResourceDescriptor`
(provider facts in), egress = `ProjectionProfile` (target shape out). Both are **facts/metadata only**;
both route authority to the bot (discovery → `SourceBinding` proposal; projection → `EgressProjection`
proposal). The `TargetIntegrationDescriptor` is the single per-target object that unifies them over one
source of API truth. Captured as the egress half of the target-boundary model.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor (/qor-plan next)._
