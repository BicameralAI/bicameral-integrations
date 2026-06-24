# ADR-0019: Target integration descriptors & projection profiles (the governed-egress shape edge)

**Date:** 2026-06-23
**Status:** Proposed (RFQ answer to GH #200; not Accepted until cross-repo sign-off — Kevin/Jin + bot #527/#528)
**Level:** L2 (declares new cross-repo-consumed concepts + the egress-shape ownership boundary)
**Relates to:** ADR-0008 (integrations are evidence adapters, not state authorities), ADR-0011 (proposed-action / review-evidence), ADR-0015 (connector config descriptor contract), ADR-0017 (provider acquisition / discovery contract — the **ingress** mirror of this ADR)
**Grounded by:** `docs/research-brief-200-projection-contract-2026-06-23.md` (META_LEDGER #223)
**Cross-repo:** BicameralAI/bicameral-bot#527 (governed egress projections — bot side), #528 (attack surface: egress may recreate external truth drift)

## Context

ADR-0017 defined the **ingress** edge: a connector discovers provider resources and fetches selected items
as **provider facts** (`ProviderResourceDescriptor` / `ProviderItemEnvelope`), never canonical authority
(ADR-0008). bot#527 now asks for the **egress** edge — *governed projections* that render canonical
Bicameral decisions into external execution surfaces (a Linear issue, a comment, later Jira/GitHub-Issues/
Slack/docs/email/CI). The ownership split places the **target-specific projection *shape*** in
`bicameral-integrations`, while the bot/sidecar retains the **governed execution**.

The product boundary:

```text
Bicameral decides what is true.
Integrations define how projections fit target tools.
External tools receive governed projections suited to their workflow.
```

`bicameral-integrations` already documents one direction through each target boundary — the connector
(ingress) side. Projections are the **opposite direction through the same boundary**, so they share the same
source of target API truth rather than spawning a parallel doc universe:

```text
Connector profile:   target system → Bicameral   (read / fetch / screen / normalize / submit evidence)
Projection profile:  Bicameral → target system   (render / create / comment / update / receipt)
Shared target docs:  one source of API truth for both directions
```

**Tension resolved (research F2).** `docs/CONNECTOR_AUTHORITY_LIMITS.md` states egress *execution* lives in
`bicameral-sidecar`/`bicameral-sdk`, "not here." This ADR **refines, not reverses** that: integrations gains
an egress **shape descriptor** (metadata only — the egress analogue of a `ProviderResourceDescriptor`); it
still does **not** execute egress, hold policy, or own receipts. A one-line clarification is added to the
authority-limits doc.

## Decision

Add three integrations-owned **metadata** objects describing governed-egress target shape. They carry **no**
permission, approval, eligibility, or authority. They are the egress mirror of ADR-0017's descriptors.

### 1. `TargetIntegrationDescriptor` — one per target system (unifies both directions)

The single object that ties a target's ingress and egress together over one source of API truth.

| Field | Type | Notes |
|---|---|---|
| `target_system` | `str` | e.g. `linear`, `github`, `jira`, `slack`. |
| `api_docs_ref` | `str` | Canonical target API documentation reference — **shared by connector + projection**. |
| `auth_scopes` | `list[str]` | Target auth scopes (read + write), shared across directions. |
| `target_surfaces` | `list[str]` | The target's addressable surfaces (`issue`, `comment`, `repository`, `channel`, …). |
| `ingress_capabilities` | `list[str]` | What the target can be **read** from (declarative; backs the connector side). |
| `egress_capabilities` | `list[str]` | What the target can be **written/rendered** to (declarative; backs projection). |
| `connector_profiles` | `list[ref]` | References to the ingress connectors (ADR-0017 / active·passive·webhook modes). |
| `projection_profiles` | `list[ProjectionProfile]` | The egress shapes (§2). |
| `target_adapters` | `list[TargetAdapter]` | Per-target operation/rendering/credential/rate-limit/receipt constraints (§3). |

### 2. `ProjectionProfile` — target shape + capability metadata ONLY

The egress analogue of `ProviderResourceDescriptor`. It describes *how a governed projection fits a target
surface*. **It must not grant permission, waive approval, decide eligibility, or create authority.**

| Field | Type | Notes |
|---|---|---|
| `profile_id` | `str` | Stable, versioned id, e.g. `linear.issue.summary.v1`. |
| `target_system` | `str` | Owning target. |
| `target_surface` | `str` | The surface this projects onto (`issue`, `comment`, …). |
| `allowed_fields` | `list[str]` | Fields a projection of this kind **may** populate. |
| `forbidden_fields` | `list[str]` | Fields it **must not** touch (e.g. assignee, status-of-record, canonical-authority fields). |
| `required_authority_label` | `str` | The authority label the **bot** must attach for this projection to be eligible — *named here, decided bot-side*. |
| `required_canonical_ref` | `bool` | Whether the projection MUST carry a back-reference to the canonical decision it renders (true for all — anti-drift, §Security). |
| `required_receipt` | `bool` | Whether the external write MUST return a receipt mapped back to the bot (true for all mutating profiles). |
| `rendering_constraints` | `dict` | Target rendering limits (length, markdown subset, field formats). |
| `mutation_capability` | `str` | The target operation this *can* drive (`create`/`update`/`comment`) — a **declaration**, not a grant. |
| `approval_class_hint` | `str` | A non-binding hint to the bot's approval routing — never an approval. |
| `reconciliation_capability` | `str` | What reconciliation the target *supports* (e.g. update-in-place vs append-only) — capability, not interpretation. |

### 3. `TargetAdapter` — per-target operation/rendering/credential/receipt constraints

| Field | Type | Notes |
|---|---|---|
| `target_system` | `str` | Owning target. |
| `supported_operations` | `list[str]` | The target write operations available (`create`/`update`/`comment`). |
| `rendering_constraints` | `dict` | Hard target limits the renderer must respect. |
| `credential_scope` | `str` | The write scope required (declared; the secret stays operator/sidecar-side — never here). |
| `rate_limit_behavior` | `str` | How the target rate-limits writes (so the executor can back off). |
| `receipt_mapping` | `dict` | How a target write result maps to a receipt `{external_id, external_url, status}` handed back to the bot. |

**Restrictions (TargetAdapter MUST NOT):** execute a mutation; hold or resolve a write credential; decide
whether a projection is eligible/approved; interpret a receipt as canonical truth. It *describes* the target
write contract; the bot/sidecar executes against it.

### 4. The authority boundary (the load-bearing rule)

> *Integrations may describe what a target can read, render, or write. Bot decides whether Bicameral may
> project anything into that target.*

**Allowed in integrations:** target API doc refs, target auth scopes, target surfaces, target read/write
capability declarations, connector profiles, projection profiles, target adapters, rendering constraints,
receipt-mapping details.

**Forbidden in integrations:** canonical-artifact eligibility decisions; projection permission decisions;
approval decisions; policy bypass; canonical state mutation; external state interpreted as Bicameral
authority.

**Bot remains sole owner of:** projection policy, approval, `EgressProjection`, `EgressReceipt`,
`EgressEligibilityCheck`, `ProjectionPolicy`, and reconciliation interpretation. This is the egress
generalization of ADR-0017 §4 (`create_provider_resource` → `ProposedAction`, governed/executed bot-side):
**every** projection is a proposed, bot-governed action; integrations only supplies the target shape.

### 5. Security — answering bot#528 (egress must not recreate external truth drift)

bot#528: a projection that writes to an external tool and then treats that external state as authoritative
would let external systems launder themselves into canonical Bicameral truth. The integrations-side design
prevents this **by construction**, not by policy:

1. **Shape-only profiles.** A `ProjectionProfile` carries no permission/approval/eligibility/authority — it
   cannot itself cause a write (mirrors discovery descriptors being provider-facts-only).
2. **`required_canonical_ref`.** Every projection back-references the canonical decision it renders; the
   external artifact is a *rendering of* canonical truth, never a *source* of it.
3. **`required_receipt` + `receipt_mapping`.** A write returns a receipt (`{external_id, external_url,
   status}`) handed to the bot; **the bot** interprets reconciliation. Integrations never reads external
   state back as Bicameral authority — `forbidden_fields` + the "external state interpreted as Bicameral
   authority" prohibition forbid it.
4. **`mutation_capability` is a declaration, not a grant.** It states what the target *can* do; the bot
   decides whether Bicameral *may* (`EgressEligibilityCheck` / `ProjectionPolicy`, bot-owned).
5. **No per-target truth model.** Profiles map *to* target shape; they never define a target-specific truth
   model (RFQ non-goal). One canonical truth (Bicameral); many target renderings.
6. **Secrets stay operator/sidecar-side** — `credential_scope` is *declared*; the write credential is never
   resolved or held in integrations (the same `SecretResolver`-stays-operator-side discipline as ingress).

### 6. First target — the Linear projection family

Reuses the **same target facts** as the Linear connector/discovery side (one `api_docs_ref`): GraphQL
`https://api.linear.app/graphql`; auth = personal API key in the **raw `Authorization` header (no Bearer)**;
surfaces `issue` + `comment`. The first family (full field-level spec in `docs/PROJECTION_CONTRACT.md`):

- `linear.issue.summary.v1` — render a governed summary onto an **issue** (`update`; Linear `issueUpdate`).
- `linear.issue.work_item.v1` — project a governed work item as a Linear **issue** (`create`; `issueCreate`).
- `linear.comment.status.v1` — a governed status note as a **comment** (`create`; `commentCreate`).

Each declares: target surface, supported operation, required + forbidden fields, rendering constraints,
required canonical-ref behavior, required receipt behavior, permission scope requirements, reconciliation
capability. **Mutation behavior is declared, not built** (RFQ non-goal — no Linear write code here).

### 7. Consumable spec + doc placement (no new doc universe)

The machine-/consumer-facing contract is `docs/PROJECTION_CONTRACT.md` — the projection counterpart of
`docs/PROVIDER_ACQUISITION_CONTRACT.md`, the same ADR↔spec split as ADR-0015 ↔ `UI_RENDERING_SPEC.md`.
Projections **share the existing target-boundary doc family** (RFQ non-goal: "do not create a new egress-only
documentation universe"); a target's API truth is declared once and consumed by both directions.

## Consequences

- The bot can render governed decisions into external tools against a typed, authority-free, shape-only
  contract — without target mechanics leaking into the bot or external truth leaking into Bicameral.
- The integrations↔bot boundary is now a **symmetric pair**: ingress `ProviderResourceDescriptor` (facts in)
  and egress `ProjectionProfile` (shape out); both metadata-only, both routing authority to the bot
  (discovery → `SourceBinding` proposal; projection → `EgressProjection` proposal).
- `CONNECTOR_AUTHORITY_LIMITS.md` gains a one-line clarification: egress *execution* stays sidecar/sdk; the
  egress *shape descriptor* is integrations-owned + authority-free.
- The change is **additive and metadata-only** — no `EgressProjection`/receipt/policy/mutation code ships
  here; no connector or runtime is touched.
- **Follow-ups (NOT this RFQ):** (a) bot-owned `EgressProjection`/`EgressReceipt`/`EgressEligibilityCheck`/
  `ProjectionPolicy` (bot#527/#528); (b) an integrations-side **projection-profile descriptor schema +
  validator** (the ADR-0015 analogue for projections) + the per-target `projection.json` exemplars; (c)
  Linear projection *execution* (sidecar/sdk) once the bot governs it.
- **Open / cross-repo (not decided here):** bot#527/#528 must confirm consumption of these three objects in
  this shape (or counter the field set); the projection-profile → shared-schema promotion timing
  (integrations owns the mapping + pin, fails first on drift — mirrors ADR-0015/ADR-0017).

## Alternatives considered

- **Put egress execution in integrations.** Rejected: violates ADR-0008 + `CONNECTOR_AUTHORITY_LIMITS.md`;
  bot#527 explicitly keeps governed execution bot/sidecar-side. Integrations owns *shape*, not *action*.
- **Let `ProjectionProfile` carry approval/eligibility** (a "ready-to-project" flag). Rejected: that is an
  authority decision (ADR-0008/0011); it would also reopen the bot#528 drift surface. Profiles are facts.
- **A standalone egress documentation tree.** Rejected: RFQ non-goal; projections share the target-boundary
  docs ("same docs, opposite direction"), one source of API truth per target.
- **A per-target canonical truth model** (mirror external state into a target-shaped Bicameral model).
  Rejected: that *is* the bot#528 drift; one canonical truth, many renderings.
- **Ship the projection-profile JSON schema + validator now.** Deferred: the ADR records the shape; the
  machine-readable schema/validator is the ADR-0015-analogue follow-up, not this RFQ.
