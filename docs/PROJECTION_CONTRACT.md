# Projection Contract

**Status:** Proposed (pending bot **BicameralAI/bicameral-bot#527** / **#528** sign-off)
**Decision record:** [ADR-0019](adr/0019-target-integration-projection-contract.md)
**Grounded by:** `docs/research-brief-200-projection-contract-2026-06-23.md`
**Answers:** GH #200
**Ingress mirror:** [`PROVIDER_ACQUISITION_CONTRACT.md`](PROVIDER_ACQUISITION_CONTRACT.md) ([ADR-0017](adr/0017-provider-acquisition-contract.md))

The machine-facing contract surface for the **governed-egress projection** edge: how the bot renders a
canonical Bicameral decision into an external execution surface (a Linear issue, a comment, later Jira/
GitHub-Issues/Slack/docs/CI) using an integrations-supplied **target shape** — without integrations gaining
any projection authority. ADR-0019 records the *decision*; this document is the *contract* the consumers
build against (the same split as ADR-0015 ↔ `UI_RENDERING_SPEC.md`, and ADR-0017 ↔
`PROVIDER_ACQUISITION_CONTRACT.md`).

> **Proposed, not built.** No projection is executed here, and no `EgressProjection`/`EgressReceipt`/
> `ProjectionPolicy` exists in integrations — those are `bicameral-bot` core (egress execution is a bot core
> function; `bicameral-sidecar` is deprecated for alpha). The shapes below are offered for
> the bot side (#527/#528) to consume or counter; nothing here is shipped behavior.

## Same target, opposite direction

A `bicameral-integrations` target boundary carries **two** directions over **one** source of API truth:

```text
Connector (ingress):   target → Bicameral   read / fetch / screen / normalize / submit evidence   (ADR-0017)
Projection (egress):   Bicameral → target   render / create / comment / update / receipt           (ADR-0019)
Shared target docs:    api_docs_ref / auth_scopes / target_surfaces — declared once, consumed both ways
```

Ingress emits **provider facts** (`ProviderResourceDescriptor`); egress emits **target shape**
(`ProjectionProfile`). Both are metadata-only; both route authority to the bot.

## Boundary

> *Integrations may describe what a target can read, render, or write. Bot decides whether Bicameral may
> project anything into that target.*

`bicameral-integrations` supplies **shape and capability metadata only**. It does **not** — and the contract
forbids — grant permission, waive approval, decide eligibility, create authority, mutate canonical state, or
interpret external state as Bicameral truth. The bot owns projection policy, approval, `EgressProjection`,
`EgressReceipt`, `EgressEligibilityCheck`, `ProjectionPolicy`, and reconciliation interpretation (ADR-0008/
0011; the egress generalization of ADR-0017 §4).

**Allowed in integrations:** target API doc refs · target auth scopes · target surfaces · target read/write
capability declarations · connector profiles · projection profiles · target adapters · rendering constraints
· receipt-mapping details.

**Forbidden in integrations:** canonical-artifact eligibility decisions · projection permission decisions ·
approval decisions · policy bypass · canonical state mutation · external state interpreted as Bicameral
authority.

## `TargetIntegrationDescriptor`

One per target system; unifies both directions over shared target facts.

| Field | Type | Required | Notes |
|---|---|---|---|
| `target_system` | `str` | yes | `linear`, `github`, `jira`, `slack`, … |
| `api_docs_ref` | `str` | yes | Canonical target API docs — **shared by connector + projection**. |
| `auth_scopes` | `list[str]` | yes | Read + write scopes, shared across directions. |
| `target_surfaces` | `list[str]` | yes | `issue`, `comment`, `repository`, `channel`, … |
| `ingress_capabilities` | `list[str]` | yes | Declarative read/fetch capabilities (backs the connector side). |
| `egress_capabilities` | `list[str]` | yes | Declarative render/write capabilities (backs projection). |
| `connector_profiles` | `list[ref]` | no | References to the ingress connectors (ADR-0017 / active·passive·webhook). |
| `projection_profiles` | `list[ProjectionProfile]` | no | The egress shapes. |
| `target_adapters` | `list[TargetAdapter]` | no | Per-target write contract constraints. |

## `ProjectionProfile`

Per-projection-kind, versioned. **Shape + capability metadata only — never authority.**

| Field | Type | Required | Notes |
|---|---|---|---|
| `profile_id` | `str` | yes | Stable + versioned, e.g. `linear.issue.summary.v1`. |
| `target_system` | `str` | yes | Owning target. |
| `target_surface` | `str` | yes | Surface projected onto. |
| `allowed_fields` | `list[str]` | yes | Fields a projection of this kind may populate. |
| `forbidden_fields` | `list[str]` | yes | Fields it must not touch. |
| `required_authority_label` | `str` | yes | Authority label the **bot** must attach for eligibility — named, decided bot-side. |
| `required_canonical_ref` | `bool` | yes | MUST carry a back-ref to the canonical decision rendered (anti-drift). |
| `required_receipt` | `bool` | yes | Mutating projections MUST return a bot-mapped receipt. |
| `rendering_constraints` | `dict` | no | Target rendering limits. |
| `mutation_capability` | `str` | yes | Target operation this can drive (`create`/`update`/`comment`) — a declaration, not a grant. |
| `approval_class_hint` | `str` | no | Non-binding routing hint to the bot — never an approval. |
| `reconciliation_capability` | `str` | no | What reconciliation the target supports — capability, not interpretation. |

**Never present:** permission, approval, eligibility, authority, secret, or canonical state.

## `TargetAdapter`

| Field | Type | Required | Notes |
|---|---|---|---|
| `target_system` | `str` | yes | Owning target. |
| `supported_operations` | `list[str]` | yes | `create`/`update`/`comment`. |
| `rendering_constraints` | `dict` | no | Hard target limits the renderer must respect. |
| `credential_scope` | `str` | yes | Declared write scope — the secret stays operator-side (bot-resolved at execution), never here. |
| `rate_limit_behavior` | `str` | no | How the target rate-limits writes (executor back-off). |
| `receipt_mapping` | `dict` | yes | Maps a target write result → `{external_id, external_url, status}` for the bot. |

**TargetAdapter MUST NOT:** execute a mutation · hold/resolve a write credential · decide eligibility/
approval · interpret a receipt as canonical truth.

## Security — projections cannot recreate external truth (answers bot#528)

By construction, not policy:

1. **Shape-only** profiles cannot cause a write.
2. **`required_canonical_ref`** — the external artifact renders canonical truth; it is never a source of it.
3. **`required_receipt` + `receipt_mapping`** — the write returns a receipt to the **bot**, which interprets
   reconciliation; integrations never reads external state back as Bicameral authority.
4. **`mutation_capability`** is a declaration; the bot decides whether Bicameral *may* project.
5. **No per-target truth model** — one canonical truth, many renderings.
6. **Secrets stay operator-side (bot-resolved at execution)** — `credential_scope` is declared, never resolved here.

## First target — the Linear projection family

Reuses the Linear connector/discovery target facts (one `api_docs_ref`): GraphQL
`https://api.linear.app/graphql`; auth = personal API key in the **raw `Authorization` header (no Bearer)**;
write scope = the API key's mutation capability (`issueCreate`/`issueUpdate`/`commentCreate`). **Declared, not
exercised** — no Linear write code ships here.

### `linear.issue.summary.v1`

| Aspect | Value |
|---|---|
| target surface | `issue` |
| supported operation | `update` (Linear `issueUpdate`) |
| required fields | `description` (the governed summary), canonical-ref marker |
| forbidden fields | `assignee`, `state`/`status`, `priority`, `team` (status-of-record fields the projection must not own) |
| rendering constraints | Linear markdown subset; description length cap |
| required canonical-ref | **yes** — the summary embeds/links the canonical decision id |
| required receipt | **yes** — `{external_id=issue id, external_url, status}` to the bot |
| permission scope | issue write (API-key mutation capability) |
| reconciliation capability | update-in-place (idempotent on the issue description) |

### `linear.issue.work_item.v1`

| Aspect | Value |
|---|---|
| target surface | `issue` |
| supported operation | `create` (Linear `issueCreate`) |
| required fields | `title`, `description`, `team` (target team for the work item), canonical-ref marker |
| forbidden fields | `assignee`, externally-managed `state` transitions, `priority` overrides |
| rendering constraints | Linear markdown subset; title length cap |
| required canonical-ref | **yes** — the new issue carries the canonical decision back-ref |
| required receipt | **yes** — `{external_id=new issue id, external_url, status}` to the bot |
| permission scope | issue create (API-key mutation capability) |
| reconciliation capability | append-only (a new issue per governed work item; dedupe is bot-side via the receipt) |

### `linear.comment.status.v1`

| Aspect | Value |
|---|---|
| target surface | `comment` |
| supported operation | `create` (Linear `commentCreate` on an issue) |
| required fields | `body` (the governed status note), parent `issue` ref, canonical-ref marker |
| forbidden fields | issue `state`/`assignee`/`priority` (a comment must not mutate the issue of record) |
| rendering constraints | Linear markdown subset; body length cap |
| required canonical-ref | **yes** — the comment links the canonical decision/update |
| required receipt | **yes** — `{external_id=comment id, external_url, status}` to the bot |
| permission scope | comment create (API-key mutation capability) |
| reconciliation capability | append-only (status history as comments) |

## Conformance (no live credentials, when a profile is later built)

A projection profile is proven offline with **golden pairs**: a canonical decision + profile → an expected
**rendered payload** (no live write) and an expected **receipt-mapping** for a recorded target response. A
passing fixture earns **Beta**; **Live** still requires the bot to govern + `bicameral-bot` (core) to execute against
real credentials (ADR-0012). A mock never writes to a real target. *(Profiles are spec-only in this RFQ; the
renderer/validator is a follow-up.)*

## Open / cross-repo (not decided here)

1. **bot#527/#528** confirm consumption of `TargetIntegrationDescriptor`/`ProjectionProfile`/`TargetAdapter`
   in this shape, or counter the field set.
2. A machine-readable **projection-profile descriptor schema + validator** (the ADR-0015 analogue) +
   per-target `projection.json` exemplars — a follow-up build, not this RFQ (integrations#205).
3. Profile → bot-protocol/shared-schema promotion timing (integrations owns the mapping + pin, fails first on
   drift — mirrors ADR-0015 / ADR-0017).
4. Bot-owned `EgressProjection`/`EgressReceipt`/`EgressEligibilityCheck`/`ProjectionPolicy` + the per-target
   projection *execution* — a **`bicameral-bot` core function** (bot#536; `bicameral-sidecar` deprecated for
   alpha) once governed.

## Short form

```text
Same target docs.
Opposite direction of data flow.
Different governance posture: integrations describes shape; bot decides projection.
```
