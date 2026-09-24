# Bicameral × Omium Integration Surface

**Date**: 2026-09-24  
**Status**: Architecture refinement / evaluation only  
**Related issue**: #308  
**Related brief**: `docs/research-brief-omium-execution-verification-2026-09-24.md`

## Purpose

This document records the intended Bicameral ↔ Omium integration surface in the context of Bicameral's narrowing product boundary.

The current Alpha planning-hook flow is an implementation/release shape, not a permanent requirement that Bicameral's final PLG surface mirror that flow. A strong candidate product boundary is a **document and decision metadata layer** that preserves the currently applicable governed truth around source material without attempting to become every downstream runtime or workflow system.

Within that shape, the integration opportunity with Omium becomes clearer rather than broader.

## Bicameral Product Boundary

Bicameral should defend metadata and authority around governed Product Contract / `GovernedDomain` truth, including:

- document and decision identity;
- recency;
- supersession;
- applicability;
- provenance;
- contradiction and unknown state;
- reconciliation between accepted truth and observed implementation/agent behavior;
- Decision Ledger lineage and authority.

The Decision Ledger remains the canonical authority behind the governed object. The metadata layer is how external systems can understand **what currently governs and why** without becoming canonical state themselves.

This keeps Bicameral narrow:

```text
External documents / tools / agents
        |
        | source artifacts + events
        v
Bicameral governed metadata boundary
  - recency
  - supersession
  - applicability
  - provenance
  - Product Contract / GovernedDomain identity
  - Decision Ledger authority
        |
        | governed context + correlation
        v
External runtime / agent / workflow
```

## Omium's Adjacent Surface

Omium belongs downstream of that governed metadata boundary as an execution-assurance evidence source.

Its role is not to determine what should govern an action. Its useful contribution is evidence about what happened after a governed action entered execution.

```text
Bicameral governed metadata / authorization context
        |
        v
Agent / runtime / governed action
        |
        v
Omium execution assurance
  - observation
  - checkpoints
  - failure / slowdown evidence
  - side-effect verification
  - recovery lifecycle evidence
        |
        | signed / attributable provider evidence
        v
bicameral-integrations
  - authenticate
  - minimize
  - redact
  - normalize
  - hash
  - classify
  - correlate
        |
        v
Bicameral gateway / Decision Ledger provenance
```

## Why the Document-Metadata Shape Improves the Integration

A document/decision metadata layer creates a cleaner external-integration model because Bicameral does not need to absorb the implementation mechanics of systems around it.

External products can contribute bounded evidence around the defended truth boundary:

- source systems contribute document and decision evidence;
- code and delivery systems contribute implementation evidence;
- observability systems contribute operational evidence;
- Omium contributes execution-verification and recovery evidence.

All of those inputs can enrich Bicameral's view of current truth while remaining replaceable external sources.

The integration principle is therefore:

> **Bicameral determines what currently governs, why it applies, and what authority exists. Omium may provide evidence about whether the resulting execution actually produced the expected state.**

That is a stronger and more durable seam than making Omium a runtime dependency or letting either system absorb the other's authority model.

## Canonical Integration Surface

### Bicameral owns

- Product Contract / `GovernedDomain` identity and state;
- Decision Ledger authority;
- recency and supersession semantics;
- applicability;
- actor/principal context;
- policy and authorization;
- review and approval requirements;
- recovery authorization;
- evidence acceptance and governance interpretation;
- canonical provenance and reconciliation state.

### Omium may provide evidence about

- execution identity and lifecycle;
- claimed versus observed outcome;
- failure or slowdown classification;
- checkpoint identity;
- decisive-step attribution;
- side-effect verification;
- recovery creation/application;
- post-recovery verification;
- provider-native timestamps, references, and receipts.

### `bicameral-integrations` owns the seam

- provider authenticity verification;
- provider schema and version handling;
- data minimization and redaction;
- source binding and provenance;
- idempotency;
- trust and data classification;
- correlation to governed Bicameral action/decision identifiers;
- provider-neutral evidence emission.

## Required Correlation

The highest-value integration requires deterministic linkage between a Bicameral-governed action and the Omium execution evidence produced downstream.

Preferred opaque lineage identifiers are:

```text
bicameral_governed_action_id
bicameral_execution_correlation_id
bicameral_policy_decision_ref
```

These are lineage references, not bearer-authority tokens.

The integration must not allow possession or replay of a correlation identifier to authorize new work.

## Recovery Boundary

Recovery is where execution assurance can accidentally cross into governance.

The boundary must remain explicit:

```text
Omium detects failed verification
        |
        v
Omium emits failure / recovery evidence
        |
        v
Bicameral evaluates current governing truth
  + policy
  + risk
  + approval
  + recovery authority
        |
        +--> escalate
        +--> require human review
        +--> authorize bounded recovery
```

`recovery.created` and `recovery.applied` are evidence about provider activity. They are not self-authorizing Bicameral decisions.

## Trust and Compliance Posture

Formal compliance certification is not the architecture boundary.

For an early-stage reciprocal evaluation, the relevant questions are concrete:

- What data leaves each trust boundary?
- Does raw prompt, response, tool, customer, or secret-bearing data transit the provider?
- How are credentials scoped and retained?
- What bytes are signed and how is replay rejected?
- What are retention and deletion guarantees?
- Can the integration prove value with synthetic/staging data before production data is introduced?

Phase 0 should therefore remain synthetic/staging-only regardless of either company's current formal compliance maturity.

Production customer data, regulated data, contractual requirements, or enterprise procurement may later impose stronger certification requirements. Those should be evaluated when they become material rather than used as a substitute for designing the trust boundary correctly now.

## Phase 0 Shape

```text
Bicameral governed context
        |
        v
Synthetic / staging agent execution
        |
        v
Omium verification
        |
        v
Signed Omium evidence
        |
        v
bicameral-integrations adapter
        |
        v
Bicameral Decision Ledger provenance
```

Phase 0 succeeds only when:

1. an exact Bicameral governed action can be correlated to the Omium execution;
2. Omium evidence is authenticated and source-bound;
3. sensitive fixture values do not escape the protected/raw boundary;
4. duplicate/replayed/unknown events fail safely;
5. verification evidence reaches Bicameral without becoming accepted truth automatically;
6. recovery evidence cannot grant recovery authority;
7. no production customer data is required.

## Non-Goals

This architecture does **not** make Omium:

- a Bicameral state authority;
- a Product Contract or Decision Ledger owner;
- a policy or approval engine for Bicameral;
- a required Bicameral runtime dependency;
- the authority for document recency or supersession;
- an automatic recovery authority;
- a replacement for `bicameral-integrations` normalization and provenance controls.

It also does not make Bicameral responsible for implementing Omium's execution tracing, verification, counterfactual replay, or recovery machinery.

## Decision

Proceed with Omium as a **P1 execution-assurance evidence integration candidate** under the existing evidence-adapter boundary.

The document-metadata / canonical Decision Ledger product direction strengthens this candidate because it gives Bicameral a clear place to attach external execution proof without expanding Bicameral into the execution-assurance layer itself.

The architectural target is not a combined product stack. It is a clean evidence loop around a defended source-of-truth boundary.

---

_Architecture refinement only. Final PLG product shape, production Omium integration, production data exchange, interactive recovery, and release admission require separate governed decisions._
