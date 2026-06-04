# Governed Bicameral Adapter Contract

Status: Draft
Owner: BicameralAI
Last updated: 2026-06-04

## Purpose

This document defines the standard contract for adapters in `bicameral-integrations`.

The adapter contract exists to prevent each connector from inventing its own worldview, because that is how integration layers become cursed swamps. All adapters should normalize external systems into consistent Bicameral evidence, candidate, event, notification, and proposed-action structures.

## Core Rule

Adapters emit normalized Bicameral records. They do not own canonical state.

External tools are sources. Bicameral is the governance and reasoning boundary.

## Adapter Responsibilities

Each adapter is responsible for:

- Connecting to an external source through approved APIs, webhooks, files, exports, or event streams
- Verifying payload authenticity where supported
- Capturing source metadata
- Normalizing timestamps
- Mapping external actors into safe actor references
- Preserving evidence references and hashes
- Classifying data sensitivity
- Classifying action risk
- Emitting Bicameral-compatible records
- Recording adapter version and mapping version
- Failing safely when payloads are unknown or malformed

Each adapter is not responsible for:

- Approving decisions
- Mutating Bicameral canonical state directly
- Executing high-risk writes without policy
- Escalating trust tier
- Suppressing source ambiguity
- Treating external fields as verified truth

## Record Types

Adapters may emit the following record types.

### Evidence Record

An observed external source artifact.

Examples:

- GitHub issue
- Linear comment
- Jira ticket update
- Slack message reference
- SARIF finding
- Sentry event
- Zoom transcript segment
- Notion page update signal

### Candidate Record

A possible Bicameral object inferred from evidence.

Examples:

- Candidate decision
- Candidate requirement
- Candidate risk
- Candidate drift event
- Candidate compliance claim
- Candidate implementation intent

### Notification Record

A message sent to an external destination.

Examples:

- Slack notification
- Teams notification
- Email summary
- Jira comment draft notification

### Proposed Action Record

A suggested external mutation requiring review or policy approval.

Examples:

- Draft GitHub PR comment
- Proposed Jira status update
- Draft Linear issue comment
- Proposed Notion page annotation

### Audit Record

An internal record of adapter behavior.

Examples:

- Webhook received
- Webhook signature verified
- Payload rejected
- Unknown event version encountered
- Redaction applied
- Credential scope denied

## Base Schema

```yaml
record_id: "uuid"
record_type: "evidence | candidate | notification | proposed_action | audit"
record_version: "1.0"
adapter:
  adapter_id: "github"
  adapter_version: "0.1.0"
  mapping_version: "2026-06-04"
source:
  provider: "github"
  source_type: "issue | pull_request | comment | webhook | alert | document | meeting | message | file"
  external_id: "provider-specific-id"
  external_url: "canonical source URL when available"
  observed_at: "ISO-8601"
  fetched_at: "ISO-8601"
  event_id: "provider event id when available"
  event_type: "provider event type when available"
actor:
  external_actor_id: "provider actor id or null"
  display_name: "redacted or normalized display name"
  actor_type: "user | bot | system | unknown"
evidence:
  title: "short title"
  excerpt: "bounded excerpt, redacted when needed"
  content_hash: "sha256"
  attachment_refs: []
  raw_payload_ref: "secure internal pointer, never public by default"
classification:
  trust_tier: "T0 | T1 | T2 | T3 | T4 | T5"
  data_class: "public | internal | confidential | restricted | regulated"
  pii_class: "none | low | moderate | high | unknown"
  action_class: "read | notify | propose | write | destructive | unknown"
  confidence: 0.0
lineage:
  parent_record_ids: []
  correlation_ids: []
  related_external_refs: []
governance:
  requires_review: true
  review_reason: "why review is or is not required"
  allowed_outputs: []
  blocked_outputs: []
  policy_refs: []
status:
  state: "accepted | rejected | pending | quarantined"
  reason: "human-readable status reason"
```

## Evidence Record Schema

```yaml
record_type: evidence
evidence_kind: "issue | pr | doc | message | alert | scan_finding | meeting | transcript | customer_signal | analytics_event"
evidence_payload:
  summary: "normalized summary"
  normalized_fields: {}
  external_labels: []
  external_status: "provider status when available"
  external_created_at: "ISO-8601"
  external_updated_at: "ISO-8601"
```

## Candidate Record Schema

```yaml
record_type: candidate
candidate_kind: "decision | requirement | risk | drift | compliance_claim | implementation_intent | customer_signal"
candidate_payload:
  title: "candidate title"
  claim: "specific normalized claim"
  rationale: "why this candidate exists"
  supporting_evidence_ids: []
  contradicted_by_evidence_ids: []
  affected_components: []
  affected_files: []
  confidence: 0.0
  recommended_next_step: "review | accept | reject | request_more_evidence | link_to_existing"
```

## Notification Record Schema

```yaml
record_type: notification
notification_payload:
  destination_provider: "slack | teams | email | webhook"
  destination_ref: "channel, user, or endpoint ref"
  message_type: "advisory | approval_request | alert | summary"
  title: "notification title"
  body: "notification body"
  linked_record_ids: []
```

## Proposed Action Record Schema

```yaml
record_type: proposed_action
proposed_action_payload:
  provider: "github | jira | linear | notion | confluence | slack | teams"
  action_type: "create_comment | update_issue | add_label | create_task | update_status | annotate_doc"
  target_ref: "external target id or URL"
  proposed_body: "draft mutation content"
  reversible: true
  required_review_level: "human | admin | owner | security | legal"
  execution_policy_ref: "policy identifier"
```

## Audit Record Schema

```yaml
record_type: audit
audit_payload:
  event: "webhook_received | signature_verified | payload_rejected | redaction_applied | scope_denied | write_blocked"
  severity: "info | warning | error | critical"
  details: {}
```

## Required Adapter Behaviors

### Payload preservation

Adapters should preserve raw payloads only as secured internal references. Raw payloads must not be exposed in normalized records unless explicitly classified and approved.

### Hashing

Evidence records should include a content hash for replay, deduplication, and provenance.

Recommended default: SHA-256 over canonicalized normalized payload.

### Redaction

Adapters must redact or tokenize sensitive content before emitting records to lower-trust layers.

Minimum redaction targets:

- Email addresses
- Phone numbers
- Access tokens
- API keys
- Session identifiers
- Customer names where policy requires anonymization
- Medical, financial, legal, or employment-sensitive details
- Secrets in logs, stack traces, and CI output

### Unknown payload handling

Unknown event types or schema versions should be quarantined, not silently accepted.

```yaml
status:
  state: quarantined
  reason: "Unknown provider event type or schema version"
```

### Idempotency

Adapters must support idempotent ingestion.

Recommended idempotency key:

```text
provider + source_type + external_id + event_id + content_hash
```

### Time normalization

All timestamps must be normalized to ISO-8601 UTC.

Adapters may preserve original provider timezone in `source.original_timezone` when useful.

### Correlation

Adapters should emit correlation hints when available:

- PR number
- Issue key
- Commit SHA
- Branch name
- File path
- Deployment ID
- Incident ID
- Meeting ID
- Document ID
- Actor ID

## Connector Capability Classes

| Capability | Meaning | Review requirement |
|---|---|---|
| Read | Fetch data from external source | None or low, depending on data class |
| Ingest | Receive webhooks/events | Signature and schema verification required |
| Notify | Send outbound notification | Review if message includes sensitive content |
| Propose | Draft mutation but do not execute | Human review required before execution |
| Write | Execute external mutation | Policy and scoped credential required |
| Destructive | Delete, revoke, close, disable, rotate, or overwrite | Restricted by default |

## Versioning

Each adapter must declare:

- Adapter version
- Mapping version
- Supported provider API version
- Supported provider webhook version if applicable
- Last documentation verification date

Example:

```yaml
adapter_id: github
adapter_version: 0.1.0
mapping_version: 2026-06-04
provider_api_version: 2022-11-28
provider_webhook_version: current
docs_verified_at: 2026-06-04
```

## Test Fixtures

Every adapter should include:

- Valid payload fixture
- Invalid signature fixture when applicable
- Unknown event fixture
- Redaction fixture
- Duplicate event fixture
- Minimal payload fixture
- Large payload fixture
- PII payload fixture
- Proposed action fixture if write-capable

## Acceptance Criteria

An adapter is not stable until it has:

- Official docs recorded in the docs index
- Trust tier assigned
- Data classification assigned
- Fixture coverage
- Redaction coverage
- Idempotency handling
- Unknown event quarantine
- Audit records
- Mapping documentation
- Explicit statement of supported and unsupported operations
