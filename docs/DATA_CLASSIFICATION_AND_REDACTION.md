# Bicameral Data Classification and Redaction Policy

Status: Draft
Owner: BicameralAI
Last updated: 2026-06-04

## Purpose

This document defines data classification and redaction requirements for Bicameral integrations.

The policy ensures that adapters minimize sensitive data exposure while preserving enough evidence for governance, review, provenance, and drift detection.

## Classification Model

| Class | Description | Examples | Default handling |
|---|---|---|---|
| Public | Safe for public disclosure | Public issue metadata, open-source repo links | Store normally |
| Internal | Organization-only data | Internal tickets, project docs, team comments | Access-controlled storage |
| Confidential | Sensitive business or technical data | Architecture details, roadmap, private incident notes | Redact where possible, restrict access |
| Restricted | Highly sensitive operational or personal data | Secrets, credentials, customer PII, security exploit details | Tokenize, minimize, or block |
| Regulated | Data subject to legal/compliance regimes | Medical, legal, financial, employment-sensitive records | Explicit compliance review required |

## PII Classification

| PII class | Meaning | Examples |
|---|---|---|
| None | No personal data detected | Public repo URL, generic error code |
| Low | Basic professional identity | Work name, work email, GitHub username |
| Moderate | Contact or account context | Customer email, phone number, CRM account name |
| High | Sensitive personal or regulated context | Medical, financial, legal, employment, government ID data |
| Unknown | Unable to classify reliably | Unstructured transcript, freeform email body |

Unknown PII classification should be treated as restricted until reviewed.

## Default Redaction Targets

Adapters should detect and redact:

- API keys
- OAuth tokens
- Personal access tokens
- Session cookies
- Refresh tokens
- Passwords
- Private keys
- Webhook secrets
- Email addresses where not necessary
- Phone numbers
- Physical addresses
- Customer identifiers where not necessary
- Government identifiers
- Payment data
- Medical details
- Legal case details
- Employment-sensitive details
- Stack traces containing secrets
- CI logs containing environment variables

## Implementation status (2026-06-05)

This policy is implemented by two composing layers in `adapter/core/`:

- **Reject (fail-closed backstop)** — `pipeline._screen_sensitive` → `sensitive.detect_sensitive`
  (FX-SEC-001) HARD-rejects any emission carrying a **secret / PHI / PAN** (AWS/GitHub-PAT/Azure/PEM/JWT
  keys; label-adjacent MRN/SSN/DOB/patient_*; Luhn-valid card numbers). Never bypassed.
- **Redact-and-pass** — `adapter/core/redaction.py::redact(text)` scrubs the FX-SEC-001 catalog classes
  (value-consuming `sensitive.redact_catalog`) **plus email and phone** to irreversible placeholders, so
  PII-dense free-text can be emitted as evidence instead of rejected. Invariant: `detect_sensitive(redact(x)) == []`
  (redaction is a strict superset of detection — see SHADOW_GENOME SG-2026-06-05-B). Connectors opt in for
  free-text bodies (e.g. `servicenow.parse_incident`, `devin.parse_session`); FX-SEC-001 remains the backstop.

**Covered automatically**: API keys / tokens / private keys / JWT (secret); SSN / DOB / MRN / patient_* (PHI,
label-adjacent); payment PANs (Luhn); email; phone. **Not auto-detected (dropped at parse by the connector
instead)**: physical addresses, free-form customer/government identifiers without a recognized label,
employment/legal details — connectors emit a safe metadata surface and never read those fields (e.g. Cursor
drops `email`/`name`/`userId`; ServiceNow drops `caller_id`; Zendesk emits subject-not-body). Extending the
auto-detector to these classes is future work.

## Redaction Modes

### Remove

Delete the value entirely.

Use when the value has no governance value.

```text
Authorization: [REDACTED]
```

### Tokenize

Replace the value with a stable token so repeated references can be correlated without exposing the original value.

```text
customer_email: pii_email_7f3a
```

### Mask

Show partial value only where operationally useful.

```text
email: k***@example.com
```

### Summarize

Replace sensitive freeform text with a non-sensitive summary.

```text
transcript_excerpt: Customer described an access issue affecting billing workflow.
```

### Pointer-only

Store a secure reference to the source without copying sensitive content.

```yaml
raw_payload_ref: secure://payload/github/12345
excerpt: "Content withheld due to restricted classification."
```

## Evidence Preservation

Redaction must not destroy provenance.

Adapters should preserve:

- Source URL or source ID
- Event ID
- Timestamp
- Actor reference when allowed
- Content hash
- Redaction method
- Classification reason
- Secure pointer to raw payload if retention is allowed

## Recommended Redaction Metadata

```yaml
redaction:
  applied: true
  method: "tokenize | mask | remove | summarize | pointer_only"
  fields_redacted:
    - "actor.email"
    - "payload.body"
  reason: "PII class moderate"
  raw_payload_retained: true
  raw_payload_ref: "secure://payload/provider/id"
```

## Destination Controls

Before sending any outbound notification, proposed action, or external write, the adapter must evaluate destination sensitivity.

| Destination | Default allowed data |
|---|---|
| Public channel | Public only |
| Internal channel | Internal, limited confidential summaries |
| Private approval channel | Internal and confidential summaries |
| Ticket comment | Depends on ticket visibility |
| Pull request comment | Public/internal depending on repo visibility |
| Email | Requires recipient validation and classification |
| External customer system | Requires explicit customer-data policy |

## Email and Transcript Handling

Email and transcript integrations are high risk.

Default requirements:

- Ingest metadata first
- Avoid full body ingestion unless explicitly enabled
- Summarize before storing where possible
- Redact recipients and personal identifiers unless required
- Do not send transcript excerpts to broad notification destinations
- Treat legal, medical, financial, and employment content as regulated

## Security Finding Handling

Security findings may contain exploit details, secrets, vulnerable paths, or attack instructions.

Default requirements:

- Store finding identifiers and severity
- Redact secrets in code snippets
- Preserve file path and line references when allowed
- Avoid broad notifications containing exploit details
- Use restricted classification for active exploit or credential leakage

## Customer Signal Handling

CRM, support, and customer success integrations are high sensitivity.

Default requirements:

- Prefer account-level summaries over person-level details
- Tokenize customer identifiers when possible
- Avoid copying full support conversations by default
- Link to source system for authorized reviewers
- Preserve impact classification without exposing unnecessary personal data

## Redaction Test Fixtures

Every adapter should include fixtures for:

- API key in payload
- OAuth token in payload
- Email address
- Phone number
- Customer name
- Secret in stack trace
- Freeform message with mixed sensitive/non-sensitive content
- Unknown classification payload
- Outbound notification with blocked restricted content

## Failure Mode

If classification or redaction fails, the adapter must fail closed.

```yaml
status:
  state: quarantined
  reason: "Redaction failed or data classification unknown"
```

## Review Requirements

Human review is required when:

- PII class is high or unknown
- Data class is restricted or regulated
- Outbound notification includes confidential content
- Proposed write includes customer, legal, medical, or financial context
- Security finding includes exploit or secret material
- Adapter cannot confidently redact payload

## Retention

Retention should be configurable by data class.

| Data class | Suggested retention posture |
|---|---|
| Public | Normal project retention |
| Internal | Normal project retention with access control |
| Confidential | Limited retention, access-controlled |
| Restricted | Minimal retention, pointer-only preferred |
| Regulated | Compliance-specific retention only |

## Implementation Guidance

Redaction should happen before normalized records leave the adapter boundary.

Adapters should emit both:

- Redacted normalized output for Bicameral processing
- Secure raw payload pointer only when retention is approved

Do not put raw payloads into logs. This should be obvious, and yet logs have historically been where secrets go to die loudly.
