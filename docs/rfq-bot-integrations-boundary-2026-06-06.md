# RFQ Response (integrations side): bot/integrations domain boundary — GH #42

**Date**: 2026-06-06 · **Author**: integrations (Kevin) · **Status**: position for RFQ #42, pre-agreement with Jin (bot)

**Nature**: this is the **integrations-side** position. Items marked **[BOT-OWNED → Jin]** are
assertions integrations needs the bot repo to confirm or counter; items marked **[AGREE]** are
proposed shared contracts. Nothing here is settled until Kevin + Jin sign off (criteria at foot).

Grounding (this repo, as built): `adapter/core/emissions.py` (`AdapterEmission`), `runtime/
gateway_mapping.py` (`emission_to_ingest_request`), `runtime/schemas/ingest_request_v1.schema.json`
(vendored bot v1, pinned @ `4f07799` 2026-06-05), `runtime/sinks.py` (`GatewaySink`), `runtime/
poll_client.py` + `poll_auth.py` + `poll_specs.py` (the live-poll fetch half, FX-RUNTIME-003),
ADR-0008/0011/0012, FX-SEC-001 (`adapter/core/pipeline.py`).

---

## Architectural premise: the adapter is a universal *ingest* funnel; egress is externalized

The whole boundary footprint stays small because of an **asymmetry**, not a symmetry — getting this
right up front motivates the per-domain stances below:

- **Ingest IS a funnel (ADR-0004).** Every connector does provider-specific parsing into ONE neutral
  `Observation`; then a single seam — `adapter.core.pipeline.normalize` — funnels all of them:
  `Observation → AdapterEmission → validate_emissions` (the FX-SEC-001 secret/PHI/PAN screen, in ONE
  place) `→ emission_to_ingest_request` (ONE mapping) `→ ONE wire envelope` (the pinned v1
  `IngestRequest`). N providers (GitHub webhook, ServiceNow poll, Cursor POST, …) collapse to **1
  neutral shape → 1 screen → 1 mapping → 1 pinned schema → 1 gate.** The bot only ever has to
  understand one envelope. This is why the ingest contract (Domains 1 + 4) is narrow.
- **Egress is NOT a symmetric funnel — and that is the design, not a gap (ADR-0008).** Integrations
  is read-only evidence. The egress side is a **thin "propose, don't execute" edge**: a
  `ProposedAction` is inert; approval/policy/execution/retry/receipts all live **bot-side**. The
  egress footprint is small because integrations' surface is *minimized* (propose-only), not because
  rich egress is funneled through an integrations pipe. (`ProposedAction` is even still partly
  conceptual today — formalizing it is Domain 2.)

One-liner: **the universal adapter funnels *ingest* to a narrow footprint; *egress* is narrow
because the authority boundary externalizes it to the bot.** A "one symmetric funnel both ways"
model would over-claim and blur ADR-0008.

---

## 1. Ingest and evidence handoff

**Exact `AdapterEmission` → `ExternalIngestEnvelope` mapping.** Today we map to the v1
`IngestRequest` via `emission_to_ingest_request` (the de-facto envelope). The current mapping carries
**title, description, source, source_type, evidence[].excerpt** and *deliberately drops* confidence,
routing_hints, advisories, and metadata. Proposed canonical mapping:

| AdapterEmission field | Envelope field | Classification |
|---|---|---|
| `title` | `title` (floored non-empty) | **source-derived fact** (connector authored) |
| `body` | `description` (floored) | **source-derived fact** |
| evidence `source_ref.url` else `source_id:ref` | `source` | **source fact** (portable id) |
| `source_id` | `source_type` | **source fact** |
| `evidence[].excerpt` | `evidence[].excerpt` | **source fact** (reviewable, screened) |
| `emission_type` (candidate/evidence/hint/advisory) | *(envelope `tags`/typed lane?)* | **hint** — **[BOT-OWNED → Jin]**: does the gate read this to choose snapshot/evidence/candidate lanes? |
| `confidence` (`ConfidenceSurface`) | *dropped* | **hint** — NOT collapsed to scalar `level`/`confidence` (SG-2026-06-02-B); bot owns judgment |
| `routing_hints` | *(advisory routing)* | **hint** — **[BOT-OWNED → Jin]**: surfaced to review routing or dropped? |
| `advisories` | *(advisory)* | **hint** |
| `metadata` | *never on the wire* | **dropped** — FX-SEC-001 does not screen metadata, so it must never cross |
| — | `level` (`DecisionLevel`) | **bot-inferred default** — daemon's call, integrations omits it |
| — | `snapshot_content` | see snapshot ownership below |

- **Source facts vs hints vs bot defaults [AGREE]**: source facts = title/description/source/
  source_type/evidence (what the connector observed, screened). Hints = emission_type, confidence,
  routing_hints, advisories (advisory; bot may use or ignore). Bot-inferred defaults = `level`,
  dedup identity, snapshot addressing, any `ActorContext`.
- **SourceSnapshot ownership [AGREE, bot-owned]**: the **bot** owns `SourceSnapshot` creation,
  content addressing, dedup, and replay-stable references. Integrations supplies a **stable,
  replay-safe `source`** (URI-preferred, else `source_type:ref` — already implemented) and the raw
  evidence excerpt; the bot content-addresses + dedups. Rationale: dedup/replay is canonical-state
  adjacent (ADR-0008 keeps state authority bot-side). **Open**: should integrations ever send
  `snapshot_content` (the v1 field exists) or only the `source` ref + excerpts? **[→ Jin]** —
  integrations' position: send excerpts, not full snapshot bodies, to keep the redaction surface
  small (FX-SEC-001 screens what we send; a full snapshot enlarges the leak surface).
- **What noisy sources may submit [AGREE]**: integrations submits **evidence + candidate-hints +
  routing-hints + advisory results**, never authoritative candidates. `emission_type` already
  encodes the producer's claim strength (evidence < hint < advisory < candidate-draft). For a noisy
  source the connector SHOULD downgrade to `emission_type="evidence"` or `"hint"` and let the bot
  gate decide promotion. **[BOT-OWNED → Jin]**: does the gate honor a per-source "max emission_type"
  ceiling, or is trust-tier the only throttle?
- **What the bot MUST reject, not normalize [AGREE]**: (a) any payload that fails the bot's ingest
  guards (size/rate/sensitive — bot #109/#131); (b) an emission whose `source`/`evidence` carries a
  secret/PHI/PAN that slipped our producer screen (defense in depth — FX-SEC-001 is fail-closed on
  our side, but the gate re-screens); (c) malformed/oversized/schema-invalid envelopes; (d) a
  `level`/authority claim from integrations (we never send one — if present, reject). Integrations'
  invariant: **we already HARD-reject secret/PHI/PAN at the producer (`validate_emissions`), so a
  conforming emission is screen-clean by construction.**

## 2. Proposed action and egress lifecycle

- **ProposedAction vs Egress [AGREE]**: a draft GitHub comment / ticket update / Slack / Notion
  annotation is a **`ProposedAction` at the integrations/mod boundary** and becomes a **bot-owned
  `Egress`** only after governance review approves it. Same artifact, two lifecycle stages across the
  boundary: integrations *proposes*, bot *governs + executes*. ADR-0011 already fixes this for PR
  comments ("emit draft GitHub PR comments only as proposed actions, not direct writes").
- **Where approval/execution/retry/audit state lives [AGREE, bot-owned]**: **all of it is
  bot-owned.** Integrations is read-only evidence (ADR-0008) and holds no approval/execution/retry
  state. The `GatewaySink` already models this: integrations emits and gets a terminal
  `201`/`GatewayEmissionError(status)`; it does not track approval or retry queues — that is the
  operator-runtime + bot's job.
- **T3 proposed-write vs T4 governed-write in object shape (not policy language) [BOT-OWNED → Jin,
  integrations proposal]**: a **T3 ProposedAction** carries `{intent, target_ref, draft_payload,
  evidence_ids, producer, confidence}` and **no execution authority** — it is inert until governed. A
  **T4 governed write** is a bot-owned `Egress` that additionally carries `{approval_ref, policy_decision,
  actor_context, idempotency_key}` and is the only shape the bot will execute. The shape difference is
  the **presence of an approval/policy/actor envelope** — integrations literally cannot construct a T4
  object (it has no `approval_ref`/`ActorContext`).
- **Can integrations emit notification records directly? [AGREE]**: **No.** Outbound publication is
  always bot-owned `Egress`. Integrations may emit an *advisory* "this would be worth notifying"
  (`AdvisoryResult` / `ProposedAction`), never the notification itself. (Consistent with ADR-0008:
  integrations are not state authorities and own no external mutation.)
- **Preserving rejected proposed actions for audit/learning without authority [AGREE]**: rejected
  ProposedActions are preserved **bot-side** in the audit/ledger view with their rejection reason;
  integrations may keep a **local, non-authoritative** learning record (ADR-0011 already calls for
  "preserve accepted, rejected, and false-positive review history as local learning evidence"). The
  learning record is evidence, never authority — it cannot re-trigger the action.

## 3. Identity, failure, and Live readiness  *(strongest integrations grounding — FX-RUNTIME-001/003)*

- **Webhook vs poll/active-fetch attribution [AGREE, implemented]**: the **delivery mode** is the
  provenance discriminator (ADR-0006 `SourceMode`). A **webhook** carries *provider provenance* —
  the connector `verify()`s the provider signature (HMAC/Svix/shared-token) and dedups by delivery id
  / body hash; the actor is the **provider**. A **poll/active fetch** carries *operator provenance* —
  the **operator runtime** initiated it with an operator-resolved secret (`SecretResolver` by
  `source_id`); the actor is the **operator**, there is no provider signature, and trust rests on TLS
  + the operator credential. This is already real in `deliver_webhook` (verify+dedup) vs `poll`
  (operator transport + auth).
- **Actor/provenance fields that must cross; what `ActorContext` stays bot-owned [BOT-OWNED → Jin,
  integrations proposal]**: integrations should cross **`{source_type, source (portable ref),
  delivery_mode (webhook|poll|active), verification (signed|unsigned-operator-poll), provider_event_id
  (webhook only)}`**. The bot owns **`ActorContext`** (operator identity, workspace, principal,
  policy scope) — integrations does not know the operator's bot-side identity and must not invent it.
  Integrations' opaque attribution ids (e.g. cursor `userId`, SG-2026-06-05-D) are *evidence*, not
  `ActorContext`.
- **Failure ownership split [AGREE]**:
  - **Integration-owned**: parse failure, signature-verify failure, malformed provider payload,
    sensitive-data producer-screen rejection (FX-SEC-001) → the connector returns `[]`/raises before
    emit; nothing reaches the bot.
  - **Operator-runtime-owned**: secret resolution, transport/TLS, cursor persistence + watermark
    two-phase commit, retry/backoff scheduling, rate-limit pacing (all the `poll_client` caller's
    job; `PollError` surfaces to the operator).
  - **Bot-owned**: governance/policy rejection (`4xx`), ingest-guard rejection (size/rate/sensitive),
    schema rejection, dedup/snapshot, approval/execution of egress.
- **When cursors advance for pollers [AGREE, integrations proposal — the crux of Domain 3]**:
  | Gateway result | Cursor action | Why |
  |---|---|---|
  | **201** (accepted) | **advance** | evidence durably ingested |
  | **4xx** policy/schema (terminal) | **advance + record terminal** | re-emitting the same payload will deterministically fail again; do not wedge the poller — surface for review |
  | **429 / 5xx / transport** (`PollError`/`GatewayEmissionError(0/5xx)`) | **do NOT advance** (retry/backoff) | transient; the same payload should be re-attempted |
  | **sensitive-data rejection** | **do NOT advance**, quarantine + alert | indicates a redaction gap — re-emit would re-fail; needs operator/connector fix, not silent skip |
  | **schema drift** (envelope rejected as malformed) | **do NOT advance**, fail the contract gate | the mapping is stale (see Domain 4); fix-forward, don't lose the cursor |

  Cursor advance is a **two-phase commit** (emit → confirm 201 → persist watermark), operator-runtime
  owned, so a crash between emit and persist re-emits (at-least-once; the bot's dedup makes it
  effectively-once). **[→ Jin]**: confirm the bot's dedup guarantees idempotency under at-least-once.
- **Concrete Live-readiness receipts [AGREE — ADR-0012 ladder, made concrete]**: **all of**: (1) a
  successful gateway **201** receipt from a configured `GatewaySink` against a real deployment; (2)
  replay/audit visibility of that evidence in the bot ledger; (3) operator config proof (the
  connector's secret resolves + transport reaches the provider); (4) source-specific auth posture
  proven (signed webhook verify, or operator-credential poll); (5) the connector's redaction policy
  active (FX-SEC-001 + any redact-and-pass). A **mock/recorded-fixture test does NOT promote to
  Live** (ADR-0012). The 7 poll connectors are at Beta (fetch half proven on recorded fixtures);
  Live is the operator wiring `GatewaySink` + a real provider.

## 4. Schema and cross-repo contract drift

- **Vendor vs consume released artifacts [AGREE, as built]**: integrations **vendors** a pinned copy
  (`runtime/schemas/ingest_request_v1.schema.json`, pinned to bot commit `4f07799` + date) for
  offline conformance, AND treats the bot's published schema as the source of truth. Vendoring buys
  stdlib-only offline CI; the pin metadata records the upstream commit so drift is detectable.
- **Backward-compat window bot owes integrations [BOT-OWNED → Jin]**: integrations' ask — a published
  schema version is **additive-only within a major** (new optional fields OK; no field removal /
  required-tightening without a major bump), with **≥1 minor version** overlap before a breaking
  major. The v1 schema is already additive-friendly (source/snapshot/evidence optional for back-compat).
- **Who owns mapping updates when bot protocol changes [AGREE]**: **integrations owns
  `emission_to_ingest_request`** (the mapping lives here). When the bot publishes a new schema,
  integrations re-pins the vendored copy + updates the mapping. The bot owns the schema; integrations
  owns the adaptation to it.
- **Conformance fixture that proves both repos agree [AGREE — proposed]**: a shared **golden
  `AdapterEmission` → expected `IngestRequest`** fixture pair, checked into BOTH repos (or a shared
  protocol package), exercising a real external-ingest path (e.g. a github PR-evidence emission).
  Integrations validates `emission_to_ingest_request(golden_ae) == golden_ir` AND that `golden_ir`
  validates against the vendored schema. **[→ Jin]**: the bot validates the same `golden_ir` ingests
  cleanly through its gate.
- **Which CI gate fails on stale mapping, and which repo fails first [AGREE — proposed]**: a
  **contract gate** in integrations CI that (a) validates `emission_to_ingest_request` output against
  the vendored schema and (b) compares the vendored schema's pinned commit against the bot's latest
  published schema (a drift check). **Integrations fails first** (it owns the mapping + the pin), so a
  bot schema change surfaces as a red integrations contract gate before any Live emission is attempted.

## 5. PR preflight / review evidence packaging

- **Which integrations objects feed `preflight.run` [BOT-OWNED → Jin, integrations proposal]**:
  `AdapterEmission`s of `emission_type="evidence"`/`"advisory"` from the evidence sources ADR-0011
  lists (git diff, changed files, test/CI output, SARIF, dependency/security scans, connector
  observations, ADRs, governance docs) plus mod `AdvisoryResult`s. These are the *evidence pack
  inputs*; `preflight.run` is bot-owned.
- **Who owns the PR evidence pack [AGREE — shared protocol concept]**: the **pack shape** is a shared
  protocol concept; integrations **produces** the evidence items, the bot **assembles + governs** the
  pack. Neither repo solely owns it — it's the same producer/governor split as Domain 1.
- **Are PR comments just proposed actions, or is a separate review-question object needed? [BOT-OWNED
  → Jin, integrations proposal]**: PR *comments* are `ProposedAction`/`Egress` (Domain 2). But a
  *review question* ("is this intentional?") is **not** a proposed mutation — integrations proposes it
  as an `AdvisoryResult`/`RoutingHint` (advisory, routes to human), and the bot may render it as a
  review-question object. Recommend a distinct **review-question** lane so questions don't masquerade
  as draft writes.
- **Which mod outputs help preflight without drifting into generic code review [AGREE]**: mods that
  produce **governance/integration-boundary** evidence (adapter-contract conformance, authority-boundary
  checks, data-classification, dependency/source-trust risk, test-adequacy) — i.e. the things a
  generic diff-commenter can't see. Deterministic checks (lint/type/test/secret) run first; AI/mod
  findings must not duplicate them (ADR-0011).
- **What supersedes/amends ADR-0011 [AGREE — proposed]**: amend ADR-0011 to **reframe "Review Bot" as
  PR-preflight / review-evidence packaging** (per #42's settled premise), explicitly: integrations
  produces evidence + proposed actions + review questions; the bot's `preflight.run` assembles +
  governs; nothing here is generic AI code review. A new ADR (or ADR-0011 amendment) should pin the
  evidence-pack shape once Jin confirms `preflight.run`'s domain model.

---

## Acceptance-criteria status

| Criterion | Status |
|---|---|
| AE → ExternalIngestEnvelope mapping agreed (Kevin+Jin) | **Drafted** (Domain 1 table); needs Jin on emission_type/routing-hint lanes |
| Snapshot/evidence/provenance/dedup ownership assigned | **Proposed** — snapshot+dedup bot-owned; source-ref+excerpt integrations-owned; needs Jin confirm |
| ProposedAction / Egress lifecycle defined both repos | **Proposed** (Domain 2); needs Jin on T3/T4 object shapes |
| Actor/provenance + cursor/failure for webhook/poll/fetch/emission | **Proposed + largely implemented** (Domain 3); needs Jin on ActorContext + dedup idempotency |
| Live-readiness evidence concrete enough to promote a connector | **Yes** (Domain 3, 5-receipt list; ADR-0012) |
| Schema-drift ownership + conformance-gate behavior agreed | **Proposed** (Domain 4); needs Jin on compat window |
| PR preflight reconciled with `preflight.run` + ADR-0011 | **Proposed** (Domain 5); needs Jin on `preflight.run` model + ADR-0011 amendment |
| Follow-up issues created only after decisions settled | **Pending** — deferred until Kevin+Jin sign-off (this is an RFQ, not implement) |

## Proposed follow-up issues (create ONLY after Kevin+Jin agree — do not implement yet)

1. **Implement the AE→envelope mapping deltas** the agreement settles (emission_type lane, routing-hint
   handling) in `runtime/gateway_mapping.py` + re-pin the vendored schema.
2. **Cross-repo conformance fixture + contract CI gate** (golden AE↔IR pair; drift check vs bot schema).
3. **Cursor-advance policy** as an operator-runtime spec (the Domain-3 table) — currently the poller
   advance/retry rules are documented here, not codified in a runtime helper.
4. **Amend ADR-0011** to the PR-preflight / review-evidence framing + pin the evidence-pack shape.
5. **Provenance fields on the wire** (`delivery_mode`/`verification`/`provider_event_id`) — extend the
   mapping once Jin confirms what the gate consumes.
