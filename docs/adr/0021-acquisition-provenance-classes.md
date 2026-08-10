# ADR-0021: Acquisition provenance is orthogonal to connector run mode

**Date:** 2026-08-10  
**Status:** Proposed  
**Review authority:** @jinhongkuan approval requested  
**Proposal issue:** #296  
**Related cross-repo proposals:** `BicameralAI/bicameral-factory#482`, `BicameralAI/bicameral-mcp#818`

## Context

Integrations currently models provider-facing execution using run modes such as `webhook`, `active`, and `passive`. Those modes describe how a connector receives or retrieves data. They do not fully describe **who authenticated the source boundary** or how many mediation layers existed between the provider and Bicameral.

Portable agent packaging and host-native integrations create a new practical path: an agent client may already have authorized access to GitHub, Slack, Drive, or another source. The host can retrieve evidence and submit it to Bicameral through MCP without requiring a second provider setup flow.

That can materially reduce setup burden, but a host-mediated fetch is not automatically equivalent to Bicameral directly verifying a provider webhook signature or polling a provider API with operator-owned credentials.

The architecture therefore needs a provenance dimension that does not destroy existing connector semantics.

## Proposed decision

Preserve existing connector run modes and add an **orthogonal acquisition provenance class**.

```text
run_mode:
  webhook | active | passive

acquisition_mode:
  direct_provider | host_mediated | local_manual
```

Run mode answers: **how did this connector operate?**

Acquisition mode answers: **through what trust/provenance boundary did this evidence reach Bicameral?**

### `direct_provider`

Use when Bicameral directly participates in the provider acquisition boundary, for example:

- a provider-signed webhook is verified by Bicameral before parse;
- Bicameral runtime polls the provider API using operator-owned/resolved credentials;
- provider-specific replay/dedup/auth semantics are enforced by the Bicameral acquisition path.

`direct_provider` does not mean the evidence is automatically trusted or canonical. Existing source trust tiers, redaction, hard screens, admission, and daemon governance still apply.

### `host_mediated`

Use when an intermediary agent/client host retrieves source data through its own authorized integration and submits that data to Bicameral.

The intermediary must be recorded. Provider refs/timestamps supplied by the host may be preserved, but Bicameral must not claim that it independently authenticated the provider payload unless equivalent verifiable proof is actually available and validated.

### `local_manual`

Use when evidence is supplied/imported by the operator or a local tool without an item-level direct provider authentication receipt.

This may include existing passive local imports where the semantics match.

## Provenance model

The exact schema location is intentionally left for implementation review so we can minimize cross-repository churn. The semantic contract should support at least:

```json
{
  "mode": "host_mediated",
  "mediator": "<host identifier>",
  "source_provider": "github",
  "provider_auth_verified_by_bicameral": false,
  "source_receipt": null
}
```

The provenance object should be created by trusted acquisition/runtime code rather than accepted verbatim as an authoritative caller claim.

A caller-controlled field saying `provider_auth_verified_by_bicameral: true` must not be sufficient to create direct-provider assurance.

## Interaction with existing connector run modes

This ADR does not remove or redefine `webhook`, `active`, or `passive`.

Examples:

```text
GitHub signed webhook:
  run_mode = webhook
  acquisition_mode = direct_provider

GitHub REST poll run by Bicameral:
  run_mode = active
  acquisition_mode = direct_provider

Local Aider git import:
  run_mode = passive
  acquisition_mode = local_manual

GitHub data retrieved through an agent host app and submitted to Bicameral:
  run_mode = passive or a future neutral submission mode at the adapter boundary
  acquisition_mode = host_mediated
```

Implementation should avoid forcing `host_mediated` into a provider connector run mode if that would distort the existing run-mode vocabulary. Acquisition provenance is the required new semantic distinction; any submission-mode naming can remain an implementation detail until the spike identifies the smallest honest schema change.

## Trust and authority boundary

1. Acquisition mode is provenance metadata, not Product authority.
2. Integrations remain evidence adapters and never become canonical Decision authorities.
3. `direct_provider` does not bypass source trust policy, redaction, Bot admission, or daemon governance.
4. `host_mediated` must not silently inherit provider-signature assurance from a direct connector.
5. This ADR does not itself change T0/T1/etc. trust-tier assignments. Any trust-policy mapping based on acquisition mode requires explicit separate review.
6. All acquisition modes must pass the same universal secret/PHI/PAN hard-screen and applicable redact-and-pass behavior before daemon delivery.
7. Provider-authenticated terminal tests must require direct-provider evidence unless the governing test explicitly accepts a different provenance class.
8. Review/debug surfaces should expose provenance when it affects interpretation or acceptance criteria.

## Receipt semantics

Where a direct provider path has verifiable receipt material, the provenance record may reference a structured receipt containing provider-specific evidence such as:

- delivery/event identifier;
- signature verification result or receipt digest;
- replay/dedup result;
- provider endpoint/contract identifier;
- acquisition timestamp;
- connector/version identity.

Host-mediated evidence may preserve host-provided source refs and host acquisition metadata, but those should be identified as mediator observations rather than a Bicameral provider-signature receipt.

## First validation spike: GitHub

Compare two real paths that converge on compatible neutral evidence:

### Direct-provider path

```text
GitHub signed webhook
  -> Bicameral verifies X-Hub-Signature-256
  -> replay/dedup
  -> provider parse/minimization
  -> Observation / AdapterEmission
  -> redaction hard screen
  -> GatewaySink
  -> daemon
  -> acquisition_mode=direct_provider
```

### Host-mediated path

```text
Agent host with authorized GitHub integration
  -> host retrieves PR/issue/evidence
  -> preserve source refs and host identity
  -> submit through Bicameral MCP/local ingest surface
  -> neutral evidence boundary
  -> redaction hard screen
  -> daemon
  -> acquisition_mode=host_mediated
```

The validation goal is compatibility without provenance collapse.

## Required implementation controls after approval

1. Typed acquisition provenance contract.
2. Trusted assignment of `provider_auth_verified_by_bicameral`.
3. Backward-compatible default/migration for existing connector emissions.
4. Direct vs host-mediated assurance matrix.
5. Negative test rejecting/stripping caller attempts to forge direct-provider verification.
6. Redaction/hard-screen tests for every acquisition class.
7. Transformation trace preserves acquisition mode end-to-end.
8. UI/review surface exposes provenance class where materially relevant.
9. Terminal test policy distinguishes direct-provider requirements from user-journey convenience tests.
10. GitHub concrete direct and host-mediated sanitized example records.

## Alternatives considered

### Replace direct connectors with host-native integrations

Rejected. Host-native integrations can reduce setup burden but do not necessarily provide equivalent provider signature, replay, scope, minimization, or receipt guarantees.

### Treat host-mediated evidence as `passive` and stop there

Rejected. `passive` describes runtime behavior but does not make the mediation/provenance difference explicit enough for trust, evidence, or terminal-test interpretation.

### Create a separate connector implementation for every host/provider pair

Rejected as the default. That risks combinatorial duplication. The first spike should prove a common provenance contract before multiplying adapters.

### Automatically lower trust tier for all host-mediated evidence

Not decided here. Provenance must be explicit first; policy can then make a reviewed decision based on actual assurance evidence.

## Consequences

Positive:

- lower-friction acquisition can coexist with higher-assurance direct connectors;
- evidence review can distinguish source name from acquisition assurance;
- host integrations can become useful without pretending to be direct provider receipts;
- existing connector mode semantics survive.

Costs:

- provenance becomes another typed field that must survive cross-repo contracts;
- UI/trace surfaces need to expose the distinction;
- historical/default behavior requires careful migration semantics;
- trust policy may need a later explicit update.

## Approval boundary

This ADR is **Proposed**. The proposal branch may contain sanitized examples only; runtime behavior should remain unchanged.

No schema migration, trust-policy change, connector replacement, or Product acceptance claim is authorized until @jinhongkuan approves this decision or an accepted successor supersedes it.
