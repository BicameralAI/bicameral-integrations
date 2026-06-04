# Bicameral Trust Tier Model

Status: Draft
Owner: BicameralAI
Last updated: 2026-06-04

## Purpose

This document defines the trust tier model for Bicameral integrations.

The trust tier model exists to classify integrations by risk, authority, data exposure, and permitted behavior. Without this, every connector becomes a cheerful little liability wearing an API badge.

## Tier Summary

| Tier | Name | Description | Default posture |
|---|---|---|---|
| T0 | Static import | Local files, exports, schemas, scan output, static artifacts | Allowed with validation |
| T1 | Authenticated read | API access to external systems without mutation | Allowed with scoped credentials |
| T2 | Event ingest and notification | Webhooks, event streams, outbound notifications | Allowed with signature validation and content controls |
| T3 | Proposed write | Drafts or proposes mutations but does not execute without review | Human review required |
| T4 | Governed write | Executes external mutations under explicit policy | Restricted and audited |
| T5 | Restricted or prohibited | High-risk, destructive, sensitive, or agentic authority surfaces | Denied unless explicitly approved |

## T0: Static Import

### Description

Static artifacts are imported without live credentials or remote write authority.

Examples:

- SARIF files
- JSON exports
- CSV exports
- SBOMs
- Local logs
- Test fixtures
- Static config snapshots

### Allowed behavior

- Parse file
- Validate schema
- Normalize evidence
- Hash content
- Emit evidence records
- Quarantine malformed files

### Disallowed behavior

- Execute file content
- Follow embedded URLs automatically
- Treat imported findings as accepted decisions
- Store secrets in normalized output

### Review posture

Usually no human review required unless data classification is restricted.

## T1: Authenticated Read

### Description

The connector uses scoped credentials to fetch data from an external system.

Examples:

- GitHub issue fetch
- Linear issue fetch
- Jira ticket fetch
- Notion page read
- Google Drive document metadata read
- Sentry event fetch

### Allowed behavior

- Read provider records
- Normalize source metadata
- Emit evidence records
- Emit candidate records
- Track fetch/audit activity

### Disallowed behavior

- Write comments
- Change status
- Modify labels
- Create records
- Delete records
- Expand scopes automatically

### Required controls

- Scoped credentials
- Credential storage outside adapter code
- Rate limit handling
- Data classification
- Audit logging

## T2: Event Ingest and Notification

### Description

The connector receives webhook/event data or sends outbound notifications.

Examples:

- GitHub webhook ingest
- Jira webhook ingest
- Slack notification
- Teams notification
- Notion webhook ingest
- PagerDuty webhook ingest

### Allowed behavior

- Receive events
- Validate signatures where supported
- Normalize payloads
- Send advisory notifications
- Send review requests

### Disallowed behavior

- Execute source-system mutations from webhook payload alone
- Send sensitive content to broad channels by default
- Trust webhook contents without verification
- Auto-approve decisions

### Required controls

- Webhook signature validation where supported
- Replay protection
- Idempotency keys
- Secret rotation support
- Notification content classification
- Destination allowlists

## T3: Proposed Write

### Description

The connector can draft or stage changes to external systems, but execution requires human review.

Examples:

- Draft GitHub PR comment
- Draft Jira ticket update
- Draft Linear issue comment
- Draft Notion page annotation
- Draft Slack approval message

### Allowed behavior

- Generate proposed action records
- Attach evidence references
- Request review
- Queue reviewed mutation for execution by approved process

### Disallowed behavior

- Execute mutation without review
- Alter external state silently
- Hide uncertainty
- Combine unrelated changes into one approval request

### Required controls

- Human approval
- Proposed action diff
- Reversibility assessment
- Actor attribution
- Audit record

## T4: Governed Write

### Description

The connector may execute external mutations under explicit policy.

Examples:

- Add a label to a GitHub issue
- Create a Jira comment
- Update a Linear issue field
- Add a Confluence annotation
- Send a Slack message to an approved channel

### Allowed behavior

- Execute narrowly scoped mutations
- Attach provenance references
- Log execution result
- Record external mutation URL or ID

### Disallowed behavior

- Destructive operations unless separately approved
- Privilege escalation
- Bulk writes without a specific policy
- Writes containing unredacted sensitive data unless destination is approved

### Required controls

- Explicit policy reference
- Scoped credentials
- Destination allowlist
- Action audit trail
- Failure rollback or manual recovery path
- Clear operator identity

## T5: Restricted or Prohibited

### Description

T5 covers integrations or operations with elevated safety, privacy, security, or business risk.

Examples:

- Shell execution
- Broad filesystem access
- Browser automation with authenticated sessions
- Database mutation
- Production deployment control
- Customer PII ingestion at scale
- Medical, legal, financial, or employment-sensitive data
- Email inbox-wide ingestion
- Destructive actions
- Autonomous agent execution against external systems

### Allowed behavior

By default: none.

T5 operations require explicit approval and a specific control design.

### Required controls for any exception

- Written risk acceptance
- Explicit scope boundary
- Least-privilege credentials
- Human approval
- Full audit logging
- Redaction and data minimization
- Emergency disable switch
- Abuse-case review
- Rollback or containment plan

## Trust Tier Assignment Rules

Assign the highest applicable tier.

Examples:

- A GitHub connector that only imports SARIF files is T0.
- A GitHub connector that reads issues via API is T1.
- A GitHub connector that receives webhooks is T2.
- A GitHub connector that drafts PR comments is T3.
- A GitHub connector that posts PR comments is T4.
- A GitHub connector that can merge PRs or delete branches is T5 unless explicitly governed.

## Data Sensitivity Overlay

Trust tier is about capability and authority. Data classification is separate.

A read-only integration may still be restricted if it handles sensitive data.

| Data class | Examples | Handling |
|---|---|---|
| Public | Public repo metadata, public docs | Normal evidence handling |
| Internal | Internal issue summaries, non-sensitive team docs | Access-controlled evidence |
| Confidential | Private architecture, customer context, internal incidents | Redaction and stricter review |
| Restricted | Secrets, credentials, security incidents, customer PII | Minimize, tokenize, or block |
| Regulated | Medical, legal, financial, employment-sensitive records | Explicit compliance review |

## Action Sensitivity Overlay

| Action class | Examples | Default review |
|---|---|---|
| Read | Fetch record | Depends on data class |
| Notify | Send message | Review if sensitive |
| Propose | Draft change | Human review |
| Write | Mutate external system | Policy required |
| Destructive | Delete, revoke, disable, merge, deploy, rotate | Restricted |

## Review Requirements

| Condition | Review required |
|---|---|
| T0 with public/internal data | Usually no |
| T1 with confidential data | Yes or policy-based |
| T2 outbound notification with sensitive content | Yes |
| Any T3 proposed write | Yes |
| Any T4 governed write | Policy required |
| Any T5 operation | Explicit approval required |
| Unknown event schema | Quarantine, then review |
| Unknown data classification | Treat as restricted until classified |

## Minimum Controls by Tier

| Control | T0 | T1 | T2 | T3 | T4 | T5 |
|---|---|---|---|---|---|---|
| Schema validation | Required | Required | Required | Required | Required | Required |
| Audit record | Recommended | Required | Required | Required | Required | Required |
| Scoped credentials | N/A | Required | Required if authenticated | Required | Required | Required |
| Signature validation | N/A | N/A | Required where supported | Required where supported | Required where supported | Required |
| Redaction | Data-dependent | Required | Required | Required | Required | Required |
| Human review | Data-dependent | Data-dependent | Data-dependent | Required | Policy-based | Required |
| Emergency disable | Recommended | Recommended | Required | Required | Required | Required |

## Prohibited Defaults

The following must be denied by default:

- Auto-merging pull requests
- Deleting issues, tickets, docs, files, or records
- Revoking user access
- Rotating secrets
- Deploying to production
- Executing shell commands
- Writing to production databases
- Sending customer-sensitive content to public or broad channels
- Ingesting full mailboxes without explicit scope and redaction
- Acting on MCP tool calls without server-level trust scoring

## Change Management

Any integration that changes tier must update:

- Integration catalog entry
- Docs index entry
- Adapter contract mapping
- Test fixtures
- Threat model if moving to T4 or T5
- Release notes
