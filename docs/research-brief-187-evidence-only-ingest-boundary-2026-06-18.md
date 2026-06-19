# Research Brief

**Date**: 2026-06-18
**Analyst**: The Qor-logic Analyst
**Target**: GH #187 — implement the evidence-only ingest boundary for source connectors (Alex-aligned)
**Scope**: What integrations must do so connector output conforms to the **SDK evidence contract** (bicameral-sdk #7, CLOSED) — provenance, raw/non-authoritative status, source/excerpt refs — and stays inside the ADR-0008 authority boundary. Cross-repo reads only (SDK owns the contract; bot owns promotion/drift; sidecar owns customer scope).

---

## Executive Summary

#187 asks integrations to make connector output a **first-class, non-authoritative `Evidence`** that conforms to the now-defined SDK contract (`bicameral-sdk/src/evidence/index.ts` + `provenance/index.ts`, GH #7 **CLOSED**). The integrations-side is **actionable now**: the one hard dependency (the SDK evidence contract) exists; the OPEN dependencies (bot #481 decision promotion, bot #484 drift, sidecar #5 Alex scope) are **downstream consumers** integrations routes to, not blockers. **The central finding is a conformance gap, not a boundary violation:** integrations already honours the *spirit* of #187 — ADR-0008 read-only posture, FX-SEC-001 screen, frozen evidence, mods that can't write canonical state — but its neutral `AdapterEmission`/`SourceEvidence`/`SourceRef` shape does **not yet map to the SDK `Evidence` shape**, and is missing the contract's two load-bearing pieces: a **`Provenance` object** (the SDK requires `{capturedAt, capturedBy: Attribution, captureMethod, pipelineVersion?, sourceHash?}` — integrations has none) and an explicit **`status: 'raw'`** non-authoritative marker. Worse, integrations' `pipeline.normalize` **hardcodes `emission_type="candidate"`** — which is exactly the "connector pre-judges a candidate decision" the SDK separates out (a connector emits *raw evidence*; candidate-extraction and promotion are the bot's job, GH #2/#481). The work is a **mapping + provenance build**, proven Beta on fixtures (the SDK consumes it), with the candidate/decision flow routed to the bot — no new connector authority.

## Findings

### 1. Dependency readiness — actionable now

| Dependency | Repo | State | Role for integrations |
|---|---|---|---|
| Evidence contracts (#7) | bicameral-sdk | **CLOSED** | The contract integrations must produce. **Hard dep — satisfied.** |
| Decision promotion (#481) | bicameral-bot | OPEN | Consumer — integrations routes candidates to it; not a blocker. |
| Contradiction/drift (#484) | bicameral-bot | OPEN | Consumer — not a blocker. |
| Alex scoped monitoring (#5) | bicameral-sidecar | OPEN | Customer-scope owner — sidecar's job, not integrations'. |

Live end-to-end is bot-gated (as ever, ADR-0012); **integrations earns Beta on recorded conformance fixtures** against the SDK shape.

### 2. The SDK evidence contract (what integrations must emit) — verified

`bicameral-sdk/src/evidence/index.ts` + `provenance/index.ts`:
- `Evidence { id, source: SourceSystemRef, excerpt: SourceExcerptRef, provenance: Provenance, status: 'raw'|'linked'|'archived', candidateExtractionIds?, decisionIds?, capturedAt }`.
- `SourceSystemRef { system, resourceId, resourceType?, url? }`.
- `SourceExcerptRef { excerpt, locator?, capturedAt? }`.
- `Provenance { capturedAt, capturedBy: Attribution{actorId, actorType: 'human'|'agent'|'system'|'connector', displayName?}, captureMethod, pipelineVersion?, sourceHash? }`.
- **Contract invariant (in-code comment):** *"Evidence is NEVER canonical. Only reviewed and promoted decisions reach canonical authority. Evidence stays raw."* `linkEvidenceToDecision` is pure/immutable and "never confers canonical authority on evidence."

### 3. Mapping + gap: integrations `AdapterEmission` → SDK `Evidence`

| SDK field | Integrations source today | Status |
|---|---|---|
| `source.system` / `resourceId` / `resourceType` / `url` | `SourceRef.source_id` / `ref` / `kind` / `url` (`adapter/core/emissions.py`) | **MATCH** (direct rename) |
| `excerpt.excerpt` / `locator` / `capturedAt` | `SourceEvidence.excerpt` / — / `timestamp` | **PARTIAL** (no `locator`) |
| `id` | `SourceEvidence.evidence_id` (often empty) | **PARTIAL** (must be populated/stable) |
| `provenance.*` | **nothing** — no Provenance object exists | **GAP** (core of #187) |
| `provenance.capturedBy.actorType='connector'` | `author` (deliberately dropped to `""`, PII) | **GAP+ALIGN** — capturer is the *connector*, not the human actor; the PII-drop is correct, the missing piece is the connector attribution |
| `provenance.captureMethod` | `Observation.mode` (WEBHOOK/ACTIVE/PASSIVE) not carried to emission | **GAP** (map mode → captureMethod) |
| `provenance.pipelineVersion` | `adapter_version` | **MATCH** (rename) |
| `provenance.sourceHash` | not computed | **GAP** (optional; GOVERNED_ADAPTER_CONTRACT §Hashing already recommends SHA-256) |
| `status='raw'` | `emission_type` ∈ {candidate,evidence,hint,advisory}; **normalize hardcodes `"candidate"`** | **DRIFT** — a connector should emit raw evidence, not pre-judge a candidate |
| `candidateExtractionIds` / `decisionIds` | none | **N/A for integrations** — these are bot-owned (promotion happens downstream) |

### 4. The boundary is already (mostly) honoured — what's missing is the *shape*, not the *posture*

`#187`'s delivery requirements vs. reality:
- *"Treat connector output as non-authoritative / prevent connectors creating canonical decisions"* → **already true** (ADR-0008; mods EM-safe; `AdapterEmission` has no canonical-write channel). The SDK `status:'raw'` makes it **explicit in the wire shape**.
- *"Preserve source system, object reference, excerpt, timestamp, provenance"* → source/ref/excerpt/timestamp **present**; **provenance is the gap**.
- *"Route candidate decisions to core review flow"* → integrations should **stop labelling emissions `candidate`** and emit raw evidence; candidate extraction/promotion routes to bot #481/#484. (The `routing_hints`/`advisories` already model "route to review".)
- *"Document connector authority limits"* → ADR-0008 + GOVERNED_ADAPTER_CONTRACT cover it; needs a short **SDK-aligned authority-limits doc** tying the emission `status:'raw'` invariant to the SDK contract.
- *"Scoped connector permissions + opt-in monitoring boundaries"* → partially integrations (trust_tier in `config.json`; the ADR-0017 discovery permission model), but **customer-scoped monitoring is sidecar #5's** — integrations exposes the capability/trust metadata, the sidecar scopes it.

## Blueprint Alignment

| Expectation | Finding | Status |
|---|---|---|
| Connector output conforms to SDK `Evidence` | shape diverges; no `Provenance`; no `status:'raw'` | **DRIFT (gap)** |
| Connector emits non-authoritative evidence, not candidates | `normalize` hardcodes `emission_type="candidate"` | **DRIFT** |
| Provenance preserved (capturedBy/method/version/hash) | none emitted | **GAP** |
| Connectors cannot write canonical state | true (ADR-0008, frozen evidence, EM-safe mods) | **MATCH** |
| Candidate promotion / drift owned downstream | bot #481/#484 (OPEN) — integrations only routes | **MATCH (by design)** |

## Recommendations

1. **(P1, build) Add a `Provenance` neutral object + an SDK-conformant evidence mapping** in `adapter/core/` — `capturedBy = Attribution(actorId=<connector source_id>, actorType="connector")` (NOT the human actor — preserves the PII-drop), `captureMethod = Observation.mode`, `pipelineVersion = adapter_version`, optional `sourceHash = sha256(canonical excerpt)`. This is the core deliverable.
2. **(P1, correctness) Stop hardcoding `emission_type="candidate"` in `pipeline.normalize`** — emit raw evidence (`status:'raw'`-equivalent); candidate extraction is downstream (bot #481). This is the single most important boundary correction.
3. **(P1, conformance proof) Add recorded golden conformance fixtures** mapping a connector `Observation` → SDK `Evidence` JSON, asserted offline (FX-RUNTIME-003 pattern); a pass earns **Beta**, Live stays bot-gated.
4. **(P2, mapping ownership)** Integrations owns + pins a vendored copy of the SDK `Evidence`/`Provenance` shape and fails first on drift (mirror the ADR-0017 §7 promotion discipline); a cross-repo conformance fixture passes both sides before the shape is treated as stable.
5. **(P2, docs)** A short **connector authority-limits** doc tying the `status:'raw'` invariant + "Evidence is never canonical" to ADR-0008 and the SDK contract; surface per-connector trust_tier as the scoped-permission metadata the sidecar consumes.
6. **(governance)** This is an L2 cross-repo conformance build. Next phase **`/qor-plan`** → implement as one integrations cycle (provenance + mapping + fixtures + docs), Beta-on-fixtures. Do **not** implement the bot-side promotion/drift (#481/#484) or sidecar scope (#5) here — integrations stays the evidence edge.

## Updated Knowledge

For `docs/SHADOW_GENOME.md`:

- **SG-2026-06-18-D (the connector emits *raw evidence*, not a *candidate*):** `pipeline.normalize` hardcoded `emission_type="candidate"`, which quietly makes the connector pre-judge a candidate decision — the exact authority creep the SDK evidence contract separates out ("Evidence is NEVER canonical; only promoted decisions reach authority"). A source connector must emit `status:'raw'` non-authoritative evidence with full **provenance** (`capturedBy=connector`, captureMethod, pipelineVersion, sourceHash); candidate-extraction and promotion are downstream (bot) concerns. The PII-drop (`author=""`) is consistent with this — the *capturer* is the connector, not the human actor, so provenance attribution is the connector id, never a surfaced human identity.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor. #187's integrations-side is actionable (SDK #7 closed); Live is bot-gated; next phase `/qor-plan`._

## Sources

- `bicameral-sdk/src/evidence/index.ts`, `bicameral-sdk/src/provenance/index.ts` (the SDK evidence contract, GH #7)
- `adapter/core/emissions.py`, `adapter/core/pipeline.py` (integrations' current neutral shape)
- `docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md`, `docs/GOVERNED_ADAPTER_CONTRACT.md`
- GH #187 (this repo); cross-repo reads: bicameral-sdk #7, bicameral-bot #481/#484, bicameral-sidecar #5
