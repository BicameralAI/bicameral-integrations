# Research Brief

**Date**: 2026-06-02
**Analyst**: The Qor-logic Analyst
**Target**: The shape of the **universal adapter** — the single contract every connector integrates *through* — in `bicameral-integrations`.
**Scope**: The connector→adapter input interface, the neutral `AdapterEmission` object model, and the downstream gateway boundary. Grounded against the *actual* integration code in `bicameral-mcp` (Python) and the protocol types in `bicameral-bot` (Rust), not against the ADR prose alone.

---

## Executive Summary

The adapter shape is **not greenfield** — both halves of its contract already exist in source, on opposite sides of a boundary that has never been formally joined. `bicameral-mcp` holds the *connector* reality (Python `SourceAdapter` protocol, provider clients, webhook handlers) and `bicameral-bot` holds the *neutral object model* reality (`Source`/`SourceSnapshot`/`SourceEvidence`/`DecisionCandidate`, multi-dimensional confidence, content-addressed provenance). The job of `bicameral-integrations` is to define the **one shared contract** that sits between them. Three material drifts must be resolved before any code lands: (1) the existing connector protocol *conflates* connector and normalization, which ADR-0004/0005 explicitly split; (2) ADR-0005's named contract objects (`AdapterEmission`, `ConfidenceSurface`, `RoutingHint`, `AdvisoryResult`) **do not exist as types anywhere** — they are net-new and must be designed; (3) there are **two** live ingest boundaries (MCP dict-based vs. bot typed `IngestPayload`), and the brief must pick which the neutral emission targets. Recommendation: model `AdapterEmission` on bicameral-bot's richer typed `IngestPayload`, not the lossy MCP dict.

---

## Reconciliation & Operator Decisions (2026-06-02, post-scaffold)

After this brief's first draft, the `/qor-organize` scaffold (`adapter/core/`, `connectors/`, `mods/`) was inspected and operator decisions recorded. **This section supersedes the affected rows below.**

### Decisions

- **D1 (Q1) — Bridge target: the bot gateway.** Emissions bridge to `bicameral-bot` `POST /api/v1/ingest`, not MCP `handle_ingest`. The MCP dict path is legacy/out of scope for this contract.
- **D2 (Q2) — Contract source of truth: schema-first (JSON Schema). [AMENDED by norm cross-check — see F8.]** Schema-first as a *discipline* is retained, but the canonical wire schema's **home is `bicameral-bot/protocol/schemas/`** (bot ADR-0002:63 owns contract vocabulary "for bot, MCP, integrations, and cloud clients"). `bicameral-integrations` owns only its internal `AdapterEmission` dataclasses (`adapter/core/emissions.py`) as *one conformant implementation* plus a **conformance test** asserting the projection against the bot-published schema. Repo language stays **Python**; the language boundary is the wire, governed by the bot-owned schema, not by shared types. This keeps our ADR-0005 "repository-owned neutral contract" scoped to the *internal* emission object, not the cross-boundary contract.
- **D3 — Bridge is a clean projection.** The emission→`IngestRequest` bridge maps only fields the adapter owns. It never manufactures canonical fields (ADR-0005:48).

### Resolved drifts (scaffold already conforms)

- ADR-0005 objects `AdapterEmission`/`ConfidenceSurface`/`RoutingHint`/`AdvisoryResult` **exist** — `adapter/core/emissions.py:31-71`.
- `producer_version` requirement (ADR-0005:46) **satisfied** by `AdapterEmission.adapter_version` — `emissions.py:67`.
- ADR-0006 three-mode interface **exists** — `adapter/core/contracts.py:18-51` + `SourceMode` enum — `capabilities.py:9-16`.

### NEW finding F7 — Clean projection (D3) is currently IMPOSSIBLE against the bot gateway as-is

Verified against `bicameral-bot/crates/bicameral-gateway/src/routes.rs:57-86`:

| Bot `IngestRequest` field | Required? | Adapter owns it? | Projection |
|---|---|---|---|
| `level: DecisionLevel` | **required**, no serde default (`routes.rs:61`) | **No** — canonical, bot-owned (ADR-0005:48) | **BLOCKED** |
| `evidence[].span_start/span_end: usize` | **required**, no default (`routes.rs:77-78`) | **No** — emission `SourceEvidence` carries `excerpt`, no spans (`emissions.py:19-28`) | **BLOCKED** |
| `evidence` non-empty | enforced — 422 `EmptyEvidence` (`routes.rs:112-120`) | Yes (ADR-0005:45) | OK |
| `title` / `description` | required | Yes (`title` / `body`) | OK — rename in bridge |
| `source` | required | Yes (`SourceRef.source_id`) | OK |
| `tags`, `source_type`, `label`, `snapshot_content` | optional (`#[serde(default)]`) | partial | OK |

A clean projection cannot emit a valid `IngestRequest`: `level` and evidence `span_start/end` are **required by the bot but not adapter-owned**. This is a **cross-repo contract requirement on `bicameral-bot`** that the bridge cannot satisfy without violating D3. Resolution options:

1. **Gateway relaxes (preferred).** Make `level` `Option`/`#[serde(default)]` and infer it during governance; make evidence spans optional (default `None` or `0..len(excerpt)`). Keeps the clean projection intact and honors ADR-0005:48.
2. **Emission enriches (rejected as default).** Carry a non-authoritative `suggested_level` as a `RoutingHint` and force connectors to compute spans. Partially violates D3 (spans become adapter-authored) and risks `suggested_level` being misread as canonical.

**Recommendation: Option 1** — open a coordinated change on `bicameral-bot` so `level` is gateway-inferred and evidence spans are optional, *before* the first bridge lands. Until then the bridge is blocked on this dependency.

### NEW finding F8 — Norm cross-check: decisions vs. mcp + bot doctrine

Verified against established doctrine in both repos (not just APIs):

| Decision | Bot doctrine | MCP doctrine | Verdict |
|---|---|---|---|
| **D1** emit to bot gateway | **AGREES** — gateway expects non-authoritative producers → candidates → governance promotion | **CONTRADICTS** the `pull → handle_ingest → confirm_watermark` two-phase orchestration norm (`cli/sync_and_brief_cli.py`, `events/sources/__init__.py`) — but *intentionally*, per ADR-0004 extraction (F6) | **OK, sanctioned.** New obligation: integrations now owns the two-phase `confirm()` after gateway ack (`adapter/core/contracts.py:33-39` preserves the shape; orchestrator is ours to build) |
| **D2** schema ownership | **CONTRADICTS** — `bicameral-bot/protocol/` "owns the public-local contract vocabulary for bot, MCP, integrations, and cloud clients" (bot `docs/adr/0002-agent-surfaces-and-bot-runtime-interface.md:63`); `protocol/schemas/` dir staged for it | **CONTRADICTS** — `contracts.py` Pydantic is canonical; changes are coordinated breaking changes (`CLAUDE.md`) | **AMENDED** (see D2): schema home = `bot/protocol/schemas/`; integrations owns impl + conformance test |
| **D3** clean projection (no `level`, no spans) | **CONTRADICTS** (= F7): `level` required (`routes.rs:61`), spans required (`routes.rs:77-82`) | **AGREES, with precedent**: `decision_level` is producer-optional, downstream-inferred — `contracts.py:528` (`#340 auto-classified when omitted`) + `ledger/adapter.py:91-106` `_classify_decision_level`; no char-span fields exist (`contracts.py:465-474`) | **D3 is the more mature doctrine.** F7 Option 1 sharpened: ask bot to port MCP's `#340` auto-classify + optional/auto-generated spans (bot spec already auto-generates spans for plain-text CLI ingest) |

Net: the decision tree is sound. Two frictions, both resolved by **deferring contract *authority* to the bot** (D2 re-scope) while keeping schema-first discipline and clean projection; D3 stays blocked on the bot F7 change.

### Still open for `/qor-plan`

- **F1** — connector/normalizer seam: `fetch_active -> list[AdapterEmission]` (`contracts.py:25`) still has connectors producing emissions directly; ADR-0004's "raw observation → universal adapter" seam is not physically present (`pipeline.validate_emissions` is a pass-through, `pipeline.py:10-17`).
- **Scaffold pointer fix** — `pipeline.py:11` says emissions feed "MCP bridges"; update to the bot-gateway bridge per D1.
- **Two-phase commit ownership** (from F8/D1) — integrations must orchestrate `confirm()` after gateway ack; this moved from MCP to us.
- **Cross-repo: publish the wire schema to `bot/protocol/schemas/`** (from F8/D2) and add the integrations conformance test against it.

---

## Findings

### F1 — The existing connector contract is *active-only* and conflates two stages

`bicameral-mcp/sources/protocol.py:24-46` defines the only existing adapter abstraction:

```python
class SourceAdapter(Protocol):           # sources/protocol.py:24
    source_id: str                        # :27
    def can_handle_url(self, url) -> bool: ...   # :31
    def fetch_active(self, url) -> dict:   ...   # :37  → returns a normalized ingest dict
```

- It is explicitly **Phase-1 active-only** (`protocol.py:1-6`, `:25`). Passive/poller is "Phase 1b" (not yet on the protocol).
- `fetch_active` returns "a *normalized ingest payload* — a plain dict that `handlers.ingest.handle_ingest` already accepts" (`protocol.py:9-12`). **The connector does the normalization itself.**
- Concrete impls confirm: `sources/github/adapter.py:200-259` and `sources/google_drive/adapter.py:131-176` each fetch *and* normalize to the MCP `decisions[]` dict.

**Implication**: ADR-0004 (`docs/adr/0004-integration-adapter-boundary.md:24-29`) splits this into **connector** (provider-facing, returns raw *observations*) + **universal adapter** (normalizes observations → emissions). Reality has no such seam — it must be introduced.

### F2 — The three operational modes exist, but as *three unrelated shapes*, not one interface

ADR-0006 (`docs/adr/0006-active-passive-webhook-modes.md:16-27`) defines active/passive/webhook as mode interfaces a connector may partially implement. In reality:

| Mode | Where it lives today | Actual signature |
|------|----------------------|------------------|
| Active fetch | `sources/<p>/adapter.py` `fetch_active` | `(url:str) -> dict` |
| Passive poll | `sources/github/poller.py:18-96` (free function, GitHub only) | `list_merged_pulls_since(*, api_key, owner, repo, updated_after) -> list` |
| Webhook | `webhooks/<p>.py` `handle()` (module function, separate from adapter) | `(*, event, delivery_id, body, signature_header) -> tuple[int,str]` |

The three modes share **no common type** today. `bicameral-bot` *does* already carry the unifying enum: `CaptureMethod { ApiPoll, Webhook, Manual, AgentExtract }` (`crates/bicameral-api/src/source.rs:41-46`) — this is the natural discriminator for the universal adapter's mode dimension.

### F3 — The neutral object model the ADRs name already half-exists in bicameral-bot (Rust)

`bicameral-bot/crates/bicameral-api/src/` is the canonical protocol (not the empty `protocol/schemas/` dir). The verified shapes:

- `Source { uri, source_type, label? }` — `source.rs:13-19` (mutable external linkage by **URI**, not path).
- `SourceSnapshot { snapshot_addr, snapshot_ref, captured_at, content?, content_hash?, capture_method? }` — `source.rs:25-36` (immutable, **content-addressed**).
- `SourceEvidenceRef { id, source_uri, snapshot_addr, snapshot_ref, pointer_type, pointer_value, excerpt, captured_at }` — `source.rs:49-59` (typed pointer + **mandatory excerpt**).
- `SourceEvidence { id, snapshot_id, span_start, span_end, excerpt, confidence:f64, extraction_method?, captured_at }` — `evidence.rs:13-25`.
- `DecisionCandidate { id, title, description, level, source, extraction_confidence, ..., evidence_refs, candidate_state, review_state, metadata }` — `candidate.rs:18-36`.
- `IngestPayload { source, snapshot?, evidence: Vec<SourceEvidence>, candidate }` — `event_store.rs:113-120`. **This is the closest existing analog to ADR-0005's `AdapterEmission`.**
- `SourceFreshness { Fresh, Stale, Offline, Unknown }` — `source.rs:62-69` (maps to ADR-0003 trust/gating).

### F4 — Confidence is *already* dimensional in the bot, and *absent* in the MCP dict

ADR-0005 contract rule "confidence is dimensional and explainable; never a single opaque score" is **affirmed by bicameral-bot** but has no single container type:

- `ExtractionConfidence { Low, Medium, High }` — `candidate.rs:142-148`, with explicit comment: "Collapsing these into one score creates cognitive debt."
- `SourceEvidence.confidence: f64` (0.0–1.0) — `evidence.rs:21`.
- `BindingConfidence { Low, Medium, High }` — `evidence.rs:111-117`.
- `SignoffState` / `ComplianceState` (separate axes) — `dashboard.rs:85-105`.

The MCP ingest dict (`contracts.py` `IngestPayload`/`IngestDecision`) carries **no confidence field at all**. So the integration adapter is the layer that must *introduce* `ConfidenceSurface`.

### F5 — There are TWO ingest boundaries; the adapter must target the typed one

- **MCP boundary**: `handle_ingest(ctx, payload:dict, source_scope, *, ingest_mode)` — `bicameral-mcp/handlers/ingest.py:502+`, dict-based, `decisions[]`/`mappings[]`, lossy (no confidence/snapshot/provenance).
- **Bot gateway boundary**: `POST /api/v1/ingest` taking `IngestRequest { title, description, level, source, tags, source_type?, label?, snapshot_content?, evidence[] }` — `bicameral-bot/crates/bicameral-gateway/src/routes.rs:57-86`; returns candidate/evidence/governance ids.

`ARCHITECTURE_PLAN.md:47` names "`bicameral-bot/protocol/` contracts" as the gateway, while ADR-0005:18 says emissions precede "any MCP-specific ingest bridge." Both can be true: the **neutral emission is bridge-agnostic**, and a thin bridge maps it to whichever downstream is live. The neutral shape should be lossless toward the *richer* target (bot's typed `IngestPayload`), with the MCP dict bridge treated as a lossy legacy adapter.

### F6 — Recent-changes audit: the connectors were built, then *backed out for this extraction*

`git log` on `bicameral-mcp/sources|webhooks`:

- `ccb831d feat(jira): active-ingest adapter + ADF flattener (#337 Jira Phase A)`
- `087ba31 feat(jira): webhook receiver — passive ingest entry point (#337 Jira Phase B)`
- `fbdd9ec chore: back Jira/Notion/Slack/Linear integrations out of dev` ← **the backout that this repository receives**

Jira/Notion/Slack/Linear reached working/partial state then were removed from `bicameral-mcp` dev. GitHub + Google Drive remain as the **reference connectors** to model the contract against. Impact on the adapter contract: **HIGH** — the contract must be provably able to express Jira (ADF/rich-text), Slack (high-noise, ADR-0003 gating), and Drive (no participants/date) without per-source leakage.

## Blueprint Alignment

| Blueprint Claim (source) | Actual Finding | Status |
|---|---|---|
| "the adapter remains one shared contract and pipeline" (ADR-0004:36) | No shared contract type exists; MCP has a per-source `SourceAdapter` that also normalizes | **DRIFT** — contract is to-be-built; connector/normalizer seam absent |
| "Connectors return raw observations; universal adapter normalizes" (ADR-0004:24-29) | `fetch_active` returns an already-normalized ingest dict (`protocol.py:9-12`) | **DRIFT** — stages conflated today |
| Object model: `SourceRef`, `SourceEvidence`, `AdapterEmission`, `ConfidenceSurface`, `RoutingHint`, `AdvisoryResult` (ADR-0005:20-26) | `SourceEvidence` exists (bot); `SourceRef`≈`Source`/`SourceEvidenceRef`; `AdapterEmission`≈`IngestPayload`; `ConfidenceSurface`/`RoutingHint`/`AdvisoryResult` **do not exist as types** | **PARTIAL DRIFT** — half exist under different names; three are net-new |
| "Confidence is dimensional and explainable" (ADR-0005:47) | Affirmed in bot (`ExtractionConfidence`, evidence `f64`, `BindingConfidence`); absent in MCP dict | **MATCH (bot) / GAP (mcp)** |
| "Every emission records the adapter or mod version" (ADR-0005:46) | No version field on MCP dict nor bot `IngestRequest`/`DecisionCandidate` | **DRIFT** — new mandatory field required |
| "Every emission has a stable source_id" (ADR-0005:44) | MCP: `source_id` on adapter; bot: `Source.uri` + `source_type` | **MATCH** (naming to be unified) |
| "Canonical state is not an adapter-owned field" (ADR-0005:48) | Affirmed: bot keeps `signoff_state`/`compliance_state` on `Decision`, not on candidate ingest | **MATCH** |
| Three modes share one lifecycle (ADR-0006) | Three unrelated shapes today; bot's `CaptureMethod` enum is the unifier | **DRIFT** — interface unification is new work |
| Source trust tiers tune routing not authority (ADR-0003) | `SourceFreshness` enum exists in bot (`source.rs:62-69`); MCP has soft/hard gate split (`ingest.py:69-91`) | **MATCH** — reuse, don't reinvent |

## Recommendations

1. **[P0] Adopt the bot's typed model as the emission target, not the MCP dict.** Define `AdapterEmission` as a Python mirror of `bicameral-bot` `IngestPayload` = `{ source: SourceRef, snapshot: SourceSnapshot?, evidence: [SourceEvidence], candidate, confidence: ConfidenceSurface, routing_hints: [RoutingHint], advisories: [AdvisoryResult], producer_version }`. This keeps the contract lossless toward governance and avoids re-flattening through the legacy decisions-dict.

2. **[P0] Split the connector seam ADR-0004 mandates.** Connector returns provider-neutral **`Observation`** objects (raw excerpt + provider ids + capture_method); the **universal adapter** is the *single* normalizer that turns any `Observation` into an `AdapterEmission`. Connectors must contain zero `decisions[]`-shaping logic (the current `fetch_active` anti-pattern).

3. **[P0] Make `ConfidenceSurface` a named-dimension container, never a scalar.** Mirror the bot's intent: separate extraction/binding/(advisory) axes. Validation must reject any single-score collapse (ADR-0002:14, ADR-0007 "must not collapse confidence").

4. **[P1] Unify the three modes behind one capability-declaring connector interface** using `CaptureMethod` as the discriminator. A connector declares `supported_modes`; active/passive/webhook each yield `Observation`s into the same adapter pipeline. Per ADR-0006:52-56, port read-only (active/poll) first; webhook last, gated on conformance tests.

5. **[P1] Add the mandatory `producer_version` field** (adapter or mod version) to every emission — ADR-0005:46 requires it and no existing type carries it.

6. **[P2] Decide and document the bridge target now** (open question below). The neutral contract is bridge-agnostic, but conformance fixtures need a concrete first bridge to assert against.

7. **[P2] Build the contract against GitHub + Drive + (backed-out) Jira fixtures** simultaneously, since Jira's ADF rich-text and Drive's missing participants/date are the two shapes most likely to expose a leaky contract (F6).

## Open Questions for the Governor — RESOLVED (see Reconciliation)

- **Q1 (bridge target): RESOLVED → bot gateway** (D1). `POST /api/v1/ingest`.
- **Q2 (language/source of truth): RESOLVED → schema-first JSON Schema, repo stays Python** (D2).
- **Q3 (structure): RESOLVED** — directory topology created via `/qor-organize` (`adapter/`, `connectors/`, `mods/`).

**New dependency raised by the decisions:** clean projection (D3) is blocked on a `bicameral-bot` gateway change (F7 Option 1 — make `level` inferred and evidence spans optional).

## Updated Knowledge

New verified facts recorded to `docs/SHADOW_GENOME.md` (created this cycle): the connector/normalizer conflation (F1), the dual ingest boundary (F5), the connector backout that seeds this repo (F6), and the bot-side canonical type locations (F3). These supersede any assumption that the adapter contract is greenfield.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
