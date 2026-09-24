# Omium Execution-Verification Integration Architecture Brief

**Date**: 2026-09-24  
**Status**: Candidate architecture / evaluation only  
**Issue**: #308  
**Target**: Omium verification and recovery platform  
**Decision scope**: Define the Bicameral integration boundary and a safe Phase 0 evidence-contract spike. This document does **not** authorize a production connector, production credentials, recovery execution, or release admission.

## Executive Summary

Omium is a strong candidate evidence source for Bicameral because its product is focused on proving whether an agent's claimed external action actually produced the expected authoritative state, then diagnosing and optionally recovering failed executions.

The proposed Bicameral relationship is intentionally narrow:

- **Bicameral owns the governed domain**: identity, authority, policy, risk, approval requirements, action constraints, recovery authorization, evidence acceptance, canonical governance provenance, and escalation.
- **Omium owns its execution-assurance mechanics**: runtime observation, checkpointing, failure detection, counterfactual attribution, side-effect verification, recovery orchestration, and provider-native verification/recovery evidence.
- **`bicameral-integrations` owns normalization at the seam**: acquisition authenticity, schema handling, minimization/redaction, source binding, content hashing, idempotency, trust/data classification, and emission of provider-neutral Bicameral evidence.

The first useful integration is therefore **evidence interoperability**, not shared orchestration.

```text
Bicameral governed authorization context
        |
        v
Agent / runtime / governed action
        |
        v
Omium observation + verification
        |
        | provider-native verification/recovery event
        v
bicameral-integrations
  verify -> minimize -> redact -> normalize -> hash -> classify
        |
        v
Bicameral gateway / governance
        |
        +--> verified-completion evidence
        +--> contradiction / failed-verification evidence
        +--> recovery proposal / escalation
```

A provider assertion such as `execution.completed` or `recovery.applied` is evidence. It is **not** automatically a Bicameral acceptance decision.

## Why This Belongs in `bicameral-integrations`

The initial Omium use case is non-interactive evidence ingestion. Omium has publicly documented signed outbound webhook support for execution and recovery lifecycle events, making the direct adapter path the least-authority surface.

This matches the repository's established interactivity test:

- evidence/provenance ingestion belongs here;
- interactive execution or recovery action belongs behind a separately governed action surface, not inside the read-only evidence adapter.

Any future Bicameral-triggered Omium recovery operation would require a separate design and must not be smuggled into this adapter by adding one convenient POST call later.

## Verified Public Upstream Surface

Verified against public Omium documentation on 2026-09-24.

### Product and docs

- Documentation entry point: https://docs.omium.ai/intro
- Platform API keys and billing: https://docs.omium.ai/docs/platform/api-keys-billing
- Project/runtime configuration and checkpoints: https://docs.omium.ai/docs/configuration/omium-toml
- Product changelog: https://omium.ai/changelog/
- Pricing and current deployment posture: https://omium.ai/pricing/
- Privacy policy: https://omium.ai/privacy/
- Terms of service: https://omium.ai/terms/
- Design partner program: https://omium.ai/partners/

### Authentication

Omium documents API keys beginning with `omium_` for CLI, SDK, and HTTP API access. HTTP requests use `X-API-Key`. The public docs recommend environment-based secret injection for CI and rotation after exposure or team changes.

For the initial inbound-evidence integration, Bicameral should prefer Omium outbound webhook verification over broad Omium API access whenever the required evidence is present in events.

### Checkpoints and runtime configuration

Omium documents project-level checkpoint configuration including enablement, interval, and retention count. The hosted execution API is documented at `https://api.omium.ai/api/v1` in project configuration.

Checkpoint existence is useful lineage metadata, but checkpoint contents must not be assumed safe for Bicameral ingestion. Raw checkpoint state may contain prompts, tool arguments, user data, secrets, or application state.

### Signed outbound events

Omium's public changelog documents outbound HTTPS webhooks for at least:

- `execution.completed`
- `execution.failed`
- `recovery.created`
- `recovery.applied`

It documents an HMAC signature header shaped as:

```text
X-Omium-Signature: t=...,v1=...
```

and states that deliveries are retried and recorded in a per-endpoint delivery log.

Before implementation, the integration must obtain and fixture the **current official event schema and signature-verification contract**. A changelog entry is sufficient to establish candidate viability but not sufficient to freeze a production parser.

### Verification and recovery behavior

Omium publicly describes:

- verification of claimed actions against authoritative external state;
- silent-failure detection where a run reports success but the expected state is absent;
- checkpoint-based recovery;
- counterfactual replay for decisive-step attribution;
- recovery lifecycle/state-machine handling;
- reuse of previously verified fixes for recurring failure signatures.

These are provider mechanics. Bicameral should consume the resulting evidence without duplicating or assuming ownership of those algorithms.

## Authority Boundary

### Bicameral owns

- governed actor and principal identity;
- authorization and policy evaluation;
- action and recovery risk classification;
- required approval level;
- allowed/blocked action constraints;
- whether Omium evidence is sufficient, contradictory, stale, or requires additional review;
- whether a recovery may execute;
- canonical governance lineage;
- final Product/Decision state.

### Omium may provide evidence about

- execution identity and lifecycle;
- claimed outcome versus observed outcome;
- authoritative side-effect checks;
- failure classification;
- checkpoint identity;
- decisive-step attribution;
- recovery creation/application;
- verification after recovery;
- provider-native timestamps and event identifiers.

### Omium must not become, through this adapter

- Bicameral policy authority;
- approval authority;
- risk authority;
- recovery-authorization authority;
- canonical Product or Decision state;
- evidence-acceptance authority;
- a required runtime dependency for Bicameral governance.

This is the ADR-0008 boundary applied to execution assurance: **external verification is evidence, not authority**.

## Candidate Evidence Mapping

The exact schema remains blocked on an official sample payload or sandbox fixture. The mapping below defines Bicameral intent without inventing provider fields.

| Omium event | Bicameral evidence kind | Minimum normalized meaning | Governance posture |
|---|---|---|---|
| `execution.completed` | `agent_execution_verification` | Omium reports an execution completed and supplies outcome/verification evidence | Evidence only; completion is not accepted merely from event name |
| `execution.failed` | `agent_execution_failure` | Omium reports execution failure or failed verification | Candidate contradiction/risk/escalation evidence |
| `recovery.created` | `agent_recovery_proposal` | Omium created a recovery record/plan | Must not imply Bicameral authorization |
| `recovery.applied` | `agent_recovery_verification` | Omium reports recovery application and associated verification state | Evidence only; high-risk recovery may still represent a governance violation if unauthorized |

The adapter should preserve when provided:

- provider event ID;
- execution ID;
- workflow/project identifier;
- recovery ID;
- checkpoint reference;
- decisive-step reference;
- expected-state reference;
- observed/verified-state reference;
- provider timestamps;
- provider-native status/classification;
- correlation identifier supplied by Bicameral before execution;
- source URL or dashboard reference when available.

Do not normalize absent provider fields by guessing them from trace text.

## Proposed Bicameral Record Shape

Illustrative only until an official payload is captured:

```yaml
record_type: evidence
adapter:
  adapter_id: omium
  adapter_version: 0.0.1
  mapping_version: 2026-09-24
source:
  provider: omium
  source_type: webhook
  external_id: <provider event id>
  event_type: <omium event type>
  observed_at: <provider timestamp>
evidence:
  title: <bounded normalized title>
  excerpt: <redacted bounded status/verification summary>
  content_hash: <sha256 canonical normalized payload>
  raw_payload_ref: <secure internal pointer>
classification:
  trust_tier: T1
  data_class: confidential
  pii_class: unknown
  action_class: read
governance:
  requires_review: true
  review_reason: external execution-verification evidence does not grant acceptance or recovery authority
status:
  state: pending
  reason: awaiting Bicameral governance evaluation
```

The final adapter should use the repository's canonical `Observation` / external-ingest path where that contract supersedes the older illustrative governed-adapter schema.

## Correlation Contract

The integration becomes materially more useful if Omium evidence can be bound to the exact Bicameral-governed action that preceded it.

Preferred correlation properties, subject to supported Omium metadata fields:

```text
bicameral_governed_action_id
bicameral_execution_correlation_id
bicameral_policy_decision_ref
```

These values identify lineage. They must not encode policy secrets or become an authority token that Omium can replay to authorize new work.

If Omium cannot carry customer metadata safely, correlation may be maintained in Bicameral through a separately persisted mapping between Omium execution IDs and governed action IDs.

## Recovery Boundary

Failure detection and recovery authorization are separate decisions.

```text
Omium detects failed verification
        |
        v
failure evidence enters Bicameral
        |
        v
Bicameral evaluates policy/risk/authority
        |
        +--> no recovery allowed -> escalate
        |
        +--> human approval required -> propose
        |
        +--> bounded automatic retry/recovery allowed
                     |
                     v
              governed recovery action
```

The adapter itself has no recovery write authority.

A later action integration must classify recovery by effect, not by the comforting word "recovery." Retrying an idempotent cache refresh is not equivalent to replaying a payment, changing production access, rewriting Git history, or sending a customer communication.

## Data and Security Posture

### Current candidate classification

- **Trust tier**: T1 initially, contingent on valid provider signature verification and source binding.
- **Data class**: confidential by default; restricted if raw trace/tool/customer data is present.
- **PII**: unknown/high-risk until payload fixtures prove otherwise.
- **Action authority in this repo**: read/event-ingest only.

### Required controls

1. Verify `X-Omium-Signature` using the provider's current documented algorithm and timestamp/replay requirements.
2. Reject or quarantine unknown event types/schema versions.
3. Apply provider-field minimization before general normalization.
4. Run deterministic sensitive-data screening/redaction before lower-trust emission.
5. Store raw payloads only through the repository's secured raw-reference pattern, never in normal evidence output.
6. Use provider event identity plus canonical content hash for deduplication/idempotency.
7. Keep Omium API keys and webhook secrets outside fixtures, logs, normalized evidence, and committed configuration.
8. Test duplicate delivery, bad signature, stale/replayed signature, unknown event, oversized payload, PII/secrets, and malformed provider timestamp paths.

## Hosted-Service and Due-Diligence Constraints

Omium's public pricing currently describes the product as hosted and states that an in-VPC collector is planned rather than shipped. The public privacy policy describes encryption/access controls and states that customer workflow data is not used to train models.

For Phase 0:

- use synthetic or purpose-built staging executions only;
- do not transmit production customer traces;
- do not transmit production secrets;
- do not grant unrestricted database credentials;
- use the minimum read-only authoritative-state access required for the test;
- document retention and deletion behavior before expanding data scope.

Current public commercial terms should also be reviewed before reciprocal sandbox access because the evaluation involves two adjacent products. Written partnership/evaluation terms should explicitly authorize interoperability evaluation and prevent a generic competitive-analysis restriction from creating ambiguity.

This is a governance/commercial review requirement, not a claim of legal interpretation.

## Phase 0: Evidence-Contract Spike

### Goal

Prove that Omium verification evidence can enter Bicameral through the standard external-evidence path while preserving source authenticity, provenance, redaction, and the governed-domain authority boundary.

### Inputs

Obtain from Omium:

- current webhook event schema/version contract;
- signed sample fixtures for the four execution/recovery events;
- signature-verification documentation;
- event retry/replay semantics;
- stable provider identifiers and timestamps;
- supported customer correlation metadata;
- a sandbox or synthetic verification workflow;
- clarification of which fields may contain raw prompt/response/tool/customer content.

### Implementation slice

1. Implement parser/normalizer for the agreed event subset.
2. Implement provider signature verification.
3. Implement idempotency and duplicate-delivery tests.
4. Apply minimization/redaction before normalized emission.
5. Preserve provider references and correlation IDs.
6. Emit only read-only evidence into the existing `GatewaySink` path.
7. Demonstrate that `recovery.created` and `recovery.applied` cannot grant recovery authority in Integrations.

### Success evidence

The spike is successful only if all of the following are demonstrated:

- valid signed events are accepted;
- invalid/stale/replayed signatures fail safely;
- duplicate delivery is idempotent;
- unknown schema/event input is quarantined;
- sensitive fixture values do not escape the protected/raw boundary;
- an Omium execution can be correlated to an exact Bicameral governed action;
- Omium verification evidence reaches the Bicameral gateway with provider provenance intact;
- a recovery event remains evidence and does not mutate policy, approval, Product, or Decision authority;
- no production customer data is required for the proof.

## Open Questions for Omium

1. What is the canonical and versioned outbound webhook payload schema?
2. What exact bytes are signed, what timestamp tolerance applies, and how should consumers reject replay?
3. Can webhook event payloads omit raw prompt/response/tool-argument content while preserving verification value?
4. Can customers attach a stable opaque correlation ID to an execution and receive it unchanged in lifecycle events?
5. What constitutes the authoritative side-effect reference for non-database actions?
6. Can verification evidence or receipts be independently checked without trusting an Omium UI conclusion?
7. Does `recovery.applied` mean a mutation was attempted, completed, or independently re-verified, and how are those states represented separately?
8. What recovery autonomy controls can be constrained by an external governance decision?
9. What data remains in Omium versus customer-controlled buckets, and what are deletion/retention guarantees by plan?
10. What contract should a third-party governance system use so Omium remains replaceable rather than becoming canonical state?

## Decision Recommendation

**Proceed with a bounded P1 architecture evaluation and synthetic Phase 0 evidence-contract spike.**

Do not yet implement production API polling, production trace export, or automated recovery.

The strongest integration thesis is:

> Bicameral determines whether an action or recovery is governed and authorized; Omium supplies evidence about whether execution produced the expected real-world state.

That seam is valuable precisely because neither product needs to become the other's authority or runtime substrate.

---

_Architecture evaluation only. Runtime implementation, production data access, recovery execution, and release admission require separate governed work._
