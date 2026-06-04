# Bicameral Integration Strategy and Candidate Harvesting

Status: Draft
Owner: BicameralAI
Last updated: 2026-06-04

## Purpose

This document defines Bicameral's product-agnostic integration strategy and explains how integration candidates may be harvested from adjacent tools, customer workflows, open-source ecosystems, and prior implementation work.

This is not an interoperability strategy with any specific adjacent product. Bicameral owns its integration strategy, governance model, adapter contract, and connector roadmap.

## Strategic Frame

Bicameral MCP is the center.

`bicameral-integrations` is the official adapter and connector layer.

External tools are evidence sources, event sources, notification destinations, or governed action surfaces.

Adjacent tools may reveal useful integration candidates, but they do not define Bicameral architecture.

## Candidate Harvesting Rule

Bicameral may harvest integration candidates from:

- Existing Bicameral connector work
- Customer workflows
- Open-source projects
- MCP ecosystem patterns
- Developer tooling ecosystems
- Security and observability ecosystems
- Prior internal implementation work
- Adjacent products or prototypes

Candidate harvesting does not imply:

- Runtime dependency
- Shared authority
- Shared governance
- Product coupling
- Shared roadmap ownership
- Shared canonical state

All harvested candidates must be independently evaluated against:

- Bicameral adapter contract
- Trust tier model
- Official documentation
- Authentication model
- Webhook/event model
- Data sensitivity
- Maintenance burden
- Security posture
- Customer demand

## Bicameral-Owned Integration Goals

Bicameral integrations should help answer these questions:

- What decision was made?
- Where did the decision originate?
- What evidence supports it?
- What evidence contradicts it?
- What implementation work claims to satisfy it?
- Has the implementation drifted from the decision?
- What risks or incidents are connected to it?
- Who or what should review it?
- What external systems should be notified?
- What external actions may be proposed under governance?

## Integration Roles

### Evidence source

A system that provides source artifacts.

Examples:

- GitHub issue
- Jira ticket
- Notion page
- SARIF file
- Sentry event
- Zoom transcript

### Event source

A system that sends change events.

Examples:

- GitHub webhook
- Linear webhook
- Notion webhook
- Microsoft Graph change notification
- PagerDuty incident webhook

### Notification destination

A system that receives Bicameral notifications.

Examples:

- Slack channel
- Teams channel
- Email summary
- Jira comment draft

### Governed action surface

A system where Bicameral may propose or execute mutations under explicit policy.

Examples:

- Draft GitHub PR comment
- Proposed Linear issue update
- Proposed Jira status transition
- Notion annotation

## Integration Design Principles

### 1. Evidence before action

All integrations should start as read-only or event-ingest adapters before any write capability is added.

### 2. Candidate before decision

External signals may create candidate decisions, requirements, risks, or drift records. They do not automatically become accepted Bicameral decisions.

### 3. Provenance before summary

Summaries are useful, but source references, hashes, timestamps, and actor metadata are mandatory.

### 4. Scope before convenience

Credentials must be scoped to the minimum required capability. Convenience does not outrank safety, despite what every OAuth consent screen seems to believe.

### 5. Review before mutation

Write-capable connectors must pass through proposed-action and review models before external mutation is allowed.

### 6. Redaction before distribution

Sensitive data must be minimized before notifications, summaries, or candidate records are sent outside the adapter boundary.

### 7. Docs before connector

No connector should be marked stable unless official API, webhook, auth, and maintenance docs are linked in the docs index.

## Integration Lifecycle

| Stage | Description | Exit criteria |
|---|---|---|
| Candidate | Integration identified as potentially viable | Added to catalog |
| Researched | Official docs reviewed | Docs index completed |
| Scoped | Initial capabilities and trust tier selected | Scope and exclusions documented |
| Mapped | External payloads mapped to adapter contract | Mapping doc and sample fixture created |
| Prototype | Adapter handles sample payloads | Fixture tests pass |
| Beta | Adapter tested against real provider account | Auth, rate limit, audit, redaction tested |
| Stable | Production-ready connector | Governance, docs, tests, versioning complete |

## Candidate Intake Template

```yaml
candidate: "Integration name"
source_of_candidate: "customer workflow | MCP ecosystem | prior internal work | open-source review | product request"
category: "source-control | project-management | docs | communication | security | observability | crm | mcp | analytics"
expected_value:
  - "decision provenance"
  - "drift detection"
  - "risk evidence"
  - "customer impact"
official_docs:
  api: ""
  webhooks: ""
  auth: ""
  changelog: ""
initial_mode: "static_import | read | event_ingest | notify | propose | write"
recommended_trust_tier: "T0 | T1 | T2 | T3 | T4 | T5"
data_risk: "public | internal | confidential | restricted | regulated | unknown"
maintenance_risk: "low | medium | high | unknown"
notes: ""
```

## Prioritization Formula

Use this scoring model for candidate ordering.

| Factor | Score range | Meaning |
|---|---:|---|
| Bicameral value | 0-5 | Decision, evidence, drift, or governance relevance |
| Customer prevalence | 0-5 | Likelihood target users already use the tool |
| API maturity | 0-5 | Quality and stability of official API/docs |
| Webhook support | 0-5 | Availability and quality of event model |
| Data risk | -5-0 | Penalizes sensitive data exposure |
| Write risk | -5-0 | Penalizes mutation/destructive capability |
| Maintenance burden | -5-0 | Penalizes instability or poor docs |

Recommended score:

```text
bicameral_value + customer_prevalence + api_maturity + webhook_support + data_risk + write_risk + maintenance_burden
```

## Independence Statement

Bicameral's integration roadmap may reference candidate ideas discovered from other tools, but Bicameral's implementation must remain independent.

Connector decisions must be justified by:

- Bicameral-native value
- Official documentation viability
- Trust tier compatibility
- Governance readiness
- User/customer demand

They must not be justified by:

- Another product already having an integration
- Convenience alone
- Tool popularity without Bicameral relevance
- Unreviewed agentic capability
- Unofficial API availability when official APIs exist

## Recommended Initial Artifact Set

The following documents should exist before large connector expansion:

- `INTEGRATION_CANDIDATE_CATALOG.md`
- `INTEGRATION_DOCS_INDEX.md`
- `GOVERNED_ADAPTER_CONTRACT.md`
- `TRUST_TIER_MODEL.md`
- `DATA_CLASSIFICATION_AND_REDACTION.md`
- `INTEGRATION_STRATEGY_AND_CANDIDATE_HARVESTING.md`
- `adr/0008-integrations-are-evidence-adapters-not-state-authorities.md`
- `adr/0009-trust-tiered-integration-governance.md`
- `adr/0010-product-agnostic-candidate-harvesting.md`

## Closing Position

Bicameral integrations should be boring in the best way: typed, traceable, scoped, testable, and governed.

The exciting part is not the connector. The exciting part is that every connector feeds a consistent decision intelligence layer instead of creating another pile of isolated tool exhaust.
