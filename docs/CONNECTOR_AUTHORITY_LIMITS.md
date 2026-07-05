# Connector Authority Limits

**Status:** Active · **Relates to:** ADR-0008, GOVERNED_ADAPTER_CONTRACT, bicameral-sdk #7 (evidence contract), GH #187

This document states, in one place, what a `bicameral-integrations` connector **may** and **may not** do with
the evidence it produces — the integrations side of the Alex-aligned evidence-only ingest boundary.

## The invariant: a connector emits raw, non-authoritative Evidence

A connector observes an external system and emits **raw evidence**. It never owns canonical state.

- Connector output maps to the SDK `Evidence` contract (`adapter/core/sdk_evidence.to_sdk_evidence`) with
  **`status: "raw"`** — always. Per the SDK contract: *"Evidence is NEVER canonical. Only reviewed and
  promoted decisions reach canonical authority. Evidence stays raw."*
- The universal adapter normalizes every Observation to an `AdapterEmission` with `emission_type="evidence"`
  (not `"candidate"` — a connector must not pre-judge a candidate decision; SG-2026-06-18-D).
- **Candidate-extraction and promotion are downstream (bot) concerns** — bot #481 (decision promotion),
  bot #484 (contradiction/drift). Integrations *routes* candidates to that review flow via `routing_hints` /
  `advisories`; it never asserts a candidate or a canonical decision itself.

## A connector MAY

- Connect to an external source through approved APIs / webhooks / files / exports.
- Verify payload authenticity (HMAC / signature) where supported.
- Normalize the payload into a neutral `Observation` → screened `AdapterEmission` → SDK `Evidence`.
- Preserve **source system, object reference, excerpt, timestamp, and provenance** (`capturedBy`,
  `captureMethod`, `pipelineVersion`, `sourceHash`).
- Surface advisory signals via EM-safe mods and route findings to human/governance review.

## A connector MUST NOT

- Own or write canonical Bicameral state (decisions, constraints).
- Approve, sign off, or mark compliance resolved.
- Treat external source claims as accepted truth, or emit a `"candidate"`/canonical decision.
- Surface a human actor's identity as the capturer — the capturer is the **connector**
  (`Attribution.actorType = "connector"`), carrying the source id (PII never surfaced; ADR-0008,
  SG-2026-06-11-D).
- Execute external mutations. Egress (propose-only writes) **execution** lives in `bicameral-sidecar` /
  `bicameral-sdk`, not here. *(Refinement, ADR-0019 / GH #200: integrations may own the egress **shape
  descriptor** — `ProjectionProfile`, metadata only, authority-free — but never executes egress, holds
  projection policy, or owns receipts. See `docs/PROJECTION_CONTRACT.md`.)*
- Leak secret/PHI/PAN — the FX-SEC-001 screen (`pipeline._screen_sensitive`, and the export's own
  `sdk_evidence._screen`) hard-rejects sensitive data before it crosses any boundary.

## Scoped permissions & opt-in monitoring

Each connector declares a **`trust_tier`** in its `config.json` — the scoped-permission metadata a consumer
(the `bicameral-sidecar`, sidecar #5 Alex monitoring) uses to decide *which* connectors a customer opts into
and at what scope. Integrations exposes the capability/trust facts; the **sidecar owns the customer-specific
monitoring scope and routing**; the **bot owns canonical promotion and authority**; the **SDK owns the shared
contracts**.

## Readiness

The SDK-conformant evidence mapping is proven **Beta** on recorded golden fixtures
(`adapter/core/tests/test_sdk_evidence.py`, FX-RUNTIME-003 pattern). **Live** end-to-end is bot-gated — the bot
must consume the `Evidence` shape (a mock never promotes to Live, ADR-0012).
