# Bicameral

Bicameral captures implementation-constraining decisions from product, code, and collaboration evidence, then routes them through review into a durable event authority.

## Language

**Decision**:
A binding constraint on implementation. Not a suggestion, opinion, note, or general product knowledge.
_Avoid_: note, feedback, request, product knowledge

**DecisionCandidate**:
An extracted claim that has not yet been accepted into the Decision Ledger. It is non-canonical until governance policy accepts a review command and the selected event store substrate materializes the event.
_Avoid_: approved decision, canonical record, source note

**SourceEvidence**:
The excerpt, pointer, payload, or provenance record that supports a candidate, binding, dependency signal, or governance result.
_Avoid_: vague context, model memory

**BindingEvidence**:
Reviewable evidence that a decision relates to a code path, symbol, diff, dependency, workflow, or deploy surface.
_Avoid_: compliance verdict, signoff, status

**Decision Ledger**:
The canonical materialized decision record derived by replaying the selected event store substrate. Durable write authority remains the event store substrate.
_Avoid_: UI page, hosted cache, dashboard database

**Ledger View**:
The human-facing surface for inspecting Decision Ledger state and emitting review commands. It is not durable authority.
_Avoid_: Decision Ledger, source of truth

**Governance policy**:
Configurable rules that decide how candidates, review commands, and evidence route to review, advisory state, materialization, or enforcement according to workspace capability.
_Avoid_: connector logic, model prompt, fixed org-chart role

**Trust tier**:
A one-to-one product and governance label for an integration capability's risk and authority. The tiers are **T0 Static import**, **T1 Authenticated read**, **T2 Event ingest and notification**, **T3 Proposed write**, **T4 Governed write**, and **T5 Restricted or prohibited**.
_Avoid_: separate product risk label, informal sensitivity label, connector status

**GovernanceResult**:
A substrate-neutral outcome of governance or conflict analysis. It can express blocking, warning, or informational intent; each substrate maps it to honest enforcement channels.
_Avoid_: CI result only, dashboard warning only

**Proposed action**:
A suggested external mutation, review comment, ticket update, or follow-up that an integration may surface for governance. It is not executed or authoritative until a governed workflow approves and performs it.
_Avoid_: direct write, automatic action, accepted decision

**Signoff**:
The ownership lifecycle on a Decision. Approval is separate from candidate acceptance and separate from code compliance.
_Avoid_: status, compliance, drift, ratification

**Status / compliance state**:
The code-compliance state for a decision. It is computed or reviewed from grounding and drift evidence, not hand-authored as signoff.
_Avoid_: signoff, approval

**Read/write path**:
Review surfaces, MCP tools, integrations, and mods emit substrate-neutral commands/evidence. Governance policy and event store adapters decide materialization.
_Avoid_: UI writes YAML, connector writes canonical decisions directly

**Integration**:
A product-facing connection from an external tool or source into Bicameral's governed decision loop. Integrations bring source evidence, candidates, hints, and proposed actions into Bicameral; adapters and mods are implementation mechanisms for that promise.
_Avoid_: arbitrary extension, standalone automation, source authority

**Integration adapter**:
A source-specific component that transforms external source data into Bicameral protocol objects.
_Avoid_: canonical writer, governance policy

**Connector readiness**:
The product-facing lifecycle for a connector: **Candidate connector** means worth building, **Beta connector** means proven end-to-end in a controlled harness, and **Live connector** means connected by an operator to a real Bicameral deployment and producing governed evidence.
_Avoid_: implementation seam, gateway status, internal runtime milestone

**EM-safe mod**:
A lightweight domain-specific extension that emits typed candidates, evidence, dependency signals, routing hints, or advisory governance results without gaining authority over canonical state.
_Avoid_: plugin with write access, policy bypass
