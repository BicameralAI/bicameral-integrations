# Runtime Architecture: Provider Acquisition Conformance Baseline

Date: 2026-07-17

Status: draft

Level: L2 cross-repo contract

Owns: the integrations boundary for provider acquisition, credential resolution, evidence emission, cursor policy, and the bot ingest gateway.

Related context: ADR-0001, ADR-0004, ADR-0005, ADR-0006, ADR-0008, ADR-0012, ADR-0016, ADR-0017, BicameralAI/bicameral-factory#65, and BicameralAI/bicameral-factory#277.

Governance gate: `bic:spec-governance-gate` advisory/no-op. This is a documentation-only baseline; it does not promote any connector to live readiness.

## Reading Guide

Read `Runtime Invariant`, `Runtime State Classification`, and `Runtime Architecture Conformance` first.

## Runtime Invariant

Integrations observe provider systems and emit screened evidence or provider facts. The bot gateway and daemon remain the only path to canonical Bicameral state. Provider credentials stay in the operator runtime and never cross the evidence envelope.

## Runtime Problem

This repository contains connectors, provider-acquisition descriptors, operator config, gateway sinks, and cursor policy. Without an ownership map, a connector can accidentally become a state authority, a credential can enter a descriptor/envelope, or a cursor can advance before the bot has acknowledged the evidence. The conformance table makes those boundaries executable.

## Goals And Non-Goals

Goals:

- Map connector, acquisition, credential, emission, cursor, and gateway seams.
- Preserve evidence-only emissions and authority-free provider descriptors.
- Make cursor advance a two-phase decision: emit, confirm bot receipt, then persist/advance in the operator runtime.
- Fail closed for secret/PII/schema violations and never silently skip a rejected batch.

Non-goals:

- No canonical Product, Decision, signoff, compliance, or approval state here.
- No provider credential persistence in Cloud, MCP, or envelopes.
- No assumption that a fixture or mocked transport makes a connector Live.
- No lifecycle behavior change; this baseline documents current contracts and known validation gaps.

## Runtime Components

| ID | C4 kind | Name / deployment | Responsibility | State ids | Multiplicity | Must not decide or mutate |
| --- | --- | --- | --- | --- | --- | --- |
| ELM-OPERATOR | Person | Connector operator | Configure credentials, select connector/mode, review terminal outcomes | STATE-CONFIG, STATE-QUARANTINE | Many operators and providers | Canonical decisions through connector code |
| ELM-CONNECTOR | Component / operator process | `connectors/*` | Call provider APIs, parse provider facts, and preserve source identity | STATE-PROVIDER-FACT | Many connectors/providers | Canonical authority or policy acceptance |
| ELM-ACQUISITION | Component / operator process | `protocol/provider_acquisition/*` | Discover/fetch descriptors and provider-item envelopes | STATE-PROVIDER-FACT | Many provider accounts/resources | Bicameral authority terms or direct event writes |
| ELM-SECRET-RESOLVER | Component / operator process | `runtime/secrets.py`, `runtime/local_config.py` | Resolve operator secrets and validate descriptor/config shape | STATE-CONFIG | One per runtime | Log, emit, or persist secret values on the wire |
| ELM-EMISSION-FUNNEL | Component / operator process | `adapter/core/emissions.py` and screening | Normalize and hard-screen evidence/emissions | STATE-EMISSION | Many batches | Bypass redaction or add authority-bearing fields |
| ELM-CURSOR-POLICY | Component / operator process | `runtime/cursor_policy.py` | Classify success, retry, quarantine, or terminal rejection | STATE-CURSOR-DECISION | One per poll delivery | Persist the cursor or own bot dedup |
| ELM-GATEWAY-SINK | Component / operator process | `runtime/sinks.py` | Send v2 `ExternalIngestEnvelope` to bot and classify receipts | STATE-EMISSION, STATE-CURSOR-DECISION | Many endpoints/runs | Interpret external receipt as canonical authority |
| ELM-BOT-GATEWAY | External container / hosted-local | `bicameral-bot` `/api/v1/external-ingest` | Validate authority-free envelope and route it through bot-owned ingest/governance | External canonical state | One or more deployed gateways | Delegate canonical decisions to integrations |

## Runtime Relationships

| ID | Source -> destination | Interaction / medium | Handoff | State / payload | Boundary crossed |
| --- | --- | --- | --- | --- | --- |
| REL-CONNECTOR-ACQUISITION | ELM-CONNECTOR -> ELM-ACQUISITION | Python protocol calls | Synchronous | Provider descriptors/items | Provider-specific to provider-neutral boundary |
| REL-SECRET-CONNECTOR | ELM-SECRET-RESOLVER -> ELM-CONNECTOR | In-process secret lookup | Synchronous; value never serialized | Credential only in operator process | Config to provider transport boundary |
| REL-ACQUISITION-FUNNEL | ELM-ACQUISITION -> ELM-EMISSION-FUNNEL | Typed observation/emission handoff | In-process | STATE-PROVIDER-FACT -> STATE-EMISSION | Provider facts to evidence boundary |
| REL-FUNNEL-SINK | ELM-EMISSION-FUNNEL -> ELM-GATEWAY-SINK | Authority-free envelope mapping | Synchronous | `ExternalIngestEnvelope` v2 | Evidence to network boundary |
| REL-SINK-BOT | ELM-GATEWAY-SINK -> ELM-BOT-GATEWAY | HTTPS POST | Synchronous receipt | Envelope and HTTP receipt | Operator runtime to bot authority boundary |
| REL-BOT-CURSOR | ELM-BOT-GATEWAY -> ELM-CURSOR-POLICY | Receipt status/reason | Synchronous decision input | 201, retryable, terminal, quarantine classification | Bot acknowledgement to operator cursor policy |

## Runtime State Classification, Authority, Persistence, And Routing

| ID | Artifact / classification | Authoritative writer | Persistence owner / location | Readers | Routing key | Mutation path / lifecycle | Prohibited fallback |
| --- | --- | --- | --- | --- | --- | --- | --- |
| STATE-CONFIG | Operator-local config and secret references | ELM-OPERATOR / ELM-SECRET-RESOLVER | Gitignored local config, env, or approved key store | Target connector only | Connector id + declared credential key | Loaded per run; secret values never emitted | Cloud/MCP/envelope secret copy |
| STATE-PROVIDER-FACT | Evidence/provider fact | ELM-CONNECTOR / ELM-ACQUISITION | Provider response/fixture until normalized | Emission funnel and operator diagnostics | Provider + stable source/resource identity | Immutable observation for one acquisition | Fact becomes canonical Decision without bot governance |
| STATE-EMISSION | Candidate/evidence envelope | ELM-EMISSION-FUNNEL | Request memory until bot receipt; bot owns downstream persistence | Gateway sink and bot gateway | Provider/source identity + idempotent item identity | Screen -> emit; retry may resend same envelope | Direct event-store write or unscreened payload |
| STATE-CURSOR-DECISION | Local scratch/operational decision | ELM-CURSOR-POLICY | Operator runtime's explicit cursor/checkpoint seam (not this policy module) | Poll runner/operator | Connector + source + cursor/watermark | Advance only after 201 or policy-approved terminal outcome; retry/quarantine otherwise | Advance before receipt, silent skip on sensitive/schema rejection |
| STATE-QUARANTINE | Audit/receipt/log | ELM-CURSOR-POLICY / operator runtime | Operator review/quarantine store | Operator and diagnostics | Connector + batch/item identity | Retained until fixed-forward/reviewed | Treat quarantine as accepted canonical state |

## State Refinement Check

Release state: no lifecycle behavior changed. Connectors remain readiness-gated provider adapters; an acquisition emits screened evidence; the gateway returns a receipt; cursor policy decides advance, retry, or quarantine.

States added, split, merged, or retired: none.

| ID | Trigger | Authority | Persistence effect |
| --- | --- | --- | --- |
| TRANS-ACQUIRE | Provider list/fetch or poll starts | Connector/acquisition seam | Produce STATE-PROVIDER-FACT in process scope |
| TRANS-EMIT | Screening passes | Emission funnel | Send STATE-EMISSION; no canonical local write |
| TRANS-RECEIPT-CLASSIFY | Bot returns status/reason | Cursor policy | Choose advance/retry/quarantine; operator runtime persists decision |
| TRANS-QUARANTINE | Sensitive data or schema drift | Cursor policy + operator review | Hold batch; do not advance cursor |

Invariants:

- No canonical state, authority, or persistence semantics changed.
- Credentials never enter descriptors, evidence envelopes, logs, or Cloud.
- Bot receipt is required before cursor advancement on successful ingest.
- Sensitive-data and schema failures do not silently advance.

Deferred: a concrete durable cursor store implementation and full real-provider live evidence for every connector.

## State Minimization Review

No new state is introduced. Connector readiness remains metadata in existing descriptors; cursor verdicts remain a policy result; quarantine remains an operational outcome. A connector-owned canonical lifecycle is rejected because it duplicates bot authority.

## Authority Ownership Matrix

| Element | Observe | Propose | Validate | Accept / materialize | Render / notify |
| --- | --- | --- | --- | --- | --- |
| ELM-CONNECTOR | Provider facts | Evidence candidate | Provider parse/auth | None | Diagnostics |
| ELM-EMISSION-FUNNEL | Candidate/evidence fields | Envelope | Secret/PII/schema screen | None | None |
| ELM-GATEWAY-SINK | Bot receipt | None | Transport response | None | Operator outcome |
| ELM-BOT-GATEWAY | Envelope | Governed candidate | Ingest/governance policy | Bot-owned canonical path | Bot projections |
| ELM-CURSOR-POLICY | Status/reason | Cursor action | Retry/terminal/quarantine classification | None; operator runtime persists | Review alert |

## Runtime Scenarios

### SCN-PROVIDER-ACQUISITION

The operator runtime resolves a connector's declared credentials, calls the provider, and turns provider-neutral descriptors/items into screened observations. Credentials remain in-process; source identity and evidence provenance are preserved.

### SCN-EVIDENCE-DELIVERY

The funnel maps the observation to `ExternalIngestEnvelope` v2, the sink posts it to the bot gateway, and a successful 201 receipt allows the operator cursor seam to advance. Bot governance determines any canonical downstream transition.

### SCN-RETRY-AND-QUARANTINE

Transport/429/5xx failure leaves the cursor unchanged for retry. Sensitive-data or schema failure quarantines without advancing. Terminal 4xx after a deterministic bot rejection may be recorded as terminal according to policy; this is not canonical acceptance.

### SCN-FORBIDDEN-CONNECTOR-AUTHORITY

A connector writes a Decision Ledger event, treats a provider row as approval, sends a credential in an envelope, or advances a cursor before receipt. This path is forbidden.

UserJourney: not applicable to this documentation-only baseline. No live connector is promoted and no cross-repo operator journey is changed by this seed.

## Event, Command, And Protocol Contracts

Provider descriptors and item envelopes carry provider facts, stable source/resource identities, screened metadata, and optional cursors. `ExternalIngestEnvelope` v2 is the only live bot gateway handoff. Credentials, local paths, authority claims, approvals, and unscreened source bodies are excluded. Cursor semantics are two-phase and idempotent; bot dedup remains bot-owned.

## Deployment And Runtime Topology

Integrations runs in an operator-controlled process and communicates with a configured bot gateway endpoint. Working directory does not select Product identity; connector/source identity and explicit runtime configuration do. Multiple connectors and provider accounts may run in one process, so secrets and cursor keys must be scoped per connector/source rather than global.

## Error, Retry, Recovery, And Observability

- Missing/unknown credentials: fail closed with key names only.
- Provider/auth/transport failure: do not emit or advance; retry according to connector policy.
- Secret/PII rejection: quarantine and alert; never silently advance.
- Schema drift: quarantine and fix-forward; do not lose the cursor.
- Crash between emit and cursor persistence: at-least-once re-emission is expected; bot dedup is authoritative.
- Logs may record connector, source id, request id, status, and outcome class, never secret values or raw sensitive payloads.

## Runtime Architecture Conformance

| ID | Source ids | Owning Module / Seam | Required behavior | Prohibited fallback | Validation obligation | Implementation evidence |
| --- | --- | --- | --- | --- | --- | --- |
| CONF-EVIDENCE-ONLY-01 | ELM-CONNECTOR, ELM-ACQUISITION, STATE-PROVIDER-FACT, SCN-FORBIDDEN-CONNECTOR-AUTHORITY | Connector/provider-acquisition protocols | Emit provider facts/evidence only; route canonical decisions through bot | Connector writes canonical state or interprets provider state as Bicameral approval | Protocol contract and negative authority tests | ADR-0001/0004/0008; provider-acquisition tests |
| CONF-SECRET-BOUNDARY-01 | ELM-SECRET-RESOLVER, STATE-CONFIG, REL-SECRET-CONNECTOR | `runtime/local_config.py` / `runtime/secrets.py` | Resolve credentials only in operator runtime and reject unknown keys/token-bearing logs | Secret in descriptor, envelope, Cloud, or diagnostic output | Secret-fixture and config-redaction tests | `runtime/tests/test_local_config.py`; `protocol/provider_acquisition/tests/test_fixture_secret_guard.py` |
| CONF-ENVELOPE-01 | REL-FUNNEL-SINK, REL-SINK-BOT, STATE-EMISSION | `adapter/core/emissions.py` / `runtime/gateway_mapping.py` | Screen and map every live emission to authority-free `ExternalIngestEnvelope` v2 | Direct provider payload, unscreened emission, or direct event-store write | Schema/contract and gateway integration test | `runtime/tests/test_gateway_mapping.py`; bot external-ingest contract |
| CONF-CURSOR-2PC-01 | ELM-CURSOR-POLICY, STATE-CURSOR-DECISION, TRANS-RECEIPT-CLASSIFY, SCN-EVIDENCE-DELIVERY | `runtime/cursor_policy.py` plus operator cursor seam | Advance only after 201/approved terminal outcome; retry or quarantine otherwise | Advance before receipt or silently skip rejected batches | Cursor policy unit, crash/replay, and integration test | `runtime/tests/test_cursor_policy.py` |
| CONF-CURSOR-ROUTING-01 | STATE-CURSOR-DECISION, ELM-CONNECTOR, SCN-RETRY-AND-QUARANTINE | Operator runner/checkpoint seam | Scope cursor/checkpoint by connector, provider/source, and item identity | Process-global cursor, cwd-derived Product, or shared connector watermark | Multi-connector/source restart/replay topology test | Planned operator-runtime persistence fixture; current policy documents owner boundary |
| CONF-LIVE-READINESS-01 | ELM-CONNECTOR, STATE-PROVIDER-FACT, SCN-PROVIDER-ACQUISITION | Connector descriptor/readiness seam | Keep fixture/contract evidence distinct from Live promotion | Mock/fixture path presented as real-provider acceptance | Readiness ladder review plus real-provider evidence when promoted | ADR-0012 and connector `config.json` readiness metadata |

## Implementation And Issue Handoff

This seed is documentation-only. Future slices must carry the `CONF-*` ids. The first implementation follow-up is `CONF-CURSOR-ROUTING-01`: identify and test the durable operator checkpoint owner across process restart and multiple provider sources.

## ADR Implications

- ADR-0001/0004/0005/0008: reaffirmed evidence-not-authority boundary.
- ADR-0006: reaffirmed active/passive cursor and webhook distinctions.
- ADR-0012/0016/0017: reaffirmed readiness, operator credentials, and provider-acquisition contracts.
- No ADR amendment proposed by this documentation seed.

## Acceptance Criteria And Validation Plan

- Stable `ELM-*`, `REL-*`, `STATE-*`, `TRANS-*`, `SCN-*`, and `CONF-*` ids cover provider, credential, emission, cursor, and gateway boundaries.
- The state table names a concrete persistence owner or explicitly marks the remaining checkpoint seam as planned evidence.
- `git diff --check` and focused cursor/config/emission/fixture tests pass.
- No connector is promoted to Live by this PR.

## Open Questions

The durable operator cursor/checkpoint store needs an implementation owner and restart evidence; this baseline intentionally records that gap rather than inventing a persistence path.

## Request Coverage

| Request | Section |
| --- | --- |
| Seed Product-repo conformance table | `Runtime Architecture Conformance` |
| Enable C4 and state/routing diagram generation | Component, relationship, and state tables |
| Prevent integration/control-plane conflation | `Runtime Invariant`, `CONF-EVIDENCE-ONLY-01`, `CONF-ENVELOPE-01` |
