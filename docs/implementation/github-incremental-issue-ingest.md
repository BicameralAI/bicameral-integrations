# GitHub Incremental Issue Ingest

## Scope

This implementation belongs entirely to `bicameral-integrations`.

The first alpha slice ingests GitHub issues and comments incrementally through the existing adapter runtime and `GatewaySink` boundary.

## Data model

```yaml
github_repository_registration:
  installation_id: string
  repository_id: string
  full_name: string
  default_branch: string
  html_url: string

github_ingest_cursor:
  repository_id: string
  stream: issues
  updated_at_watermark: timestamp
  last_provider_event_id: string
  schema_version: 1

github_issue_observation:
  repository_id: string
  repository_full_name: string
  issue_number: integer
  issue_node_id: string
  issue_state: open | closed
  canonical_url: string
  source_version: string
  occurred_at: timestamp
  actor_login: string
  actor_type: User | Bot | Organization | unknown
  title: string
  body: string
  labels: [string]
  milestone: string | null
  assignees: [string]
  linked_pull_requests: [string]
  comment:
    id: string
    author_login: string
    author_type: User | Bot | Organization | unknown
    body: string
    created_at: timestamp
    updated_at: timestamp
  delivery:
    mode: webhook | poll
    provider_event_id: string
    verification: signed | unsigned
```

## Mapping

Each normalized observation becomes an `AdapterEmission` with:

- `source_id = github`
- `emission_type = evidence`
- stable issue or comment `SourceRef`
- screened title, body, and excerpts
- `ProviderProvenance` carrying delivery mode, signature posture, event id, and resource id
- advisory labels for automated or low-signal provider content

The existing `emission_to_external_envelope` mapping remains the only Bot handoff. GitHub-specific fields that are not part of the neutral envelope remain connector-local metadata.

## Cursor protocol

```text
fetch webhook or polling batch
  -> verify and normalize
  -> screen
  -> emit through GatewaySink
  -> require HTTP 201
  -> persist proposed cursor
```

A crash after HTTP 201 and before cursor persistence may redeliver the same observation. Bot-side deduplication is expected. Integrations must preserve a deterministic provider event id and source version so replay is observable and safe.

## Alpha acceptance

- GitHub App installation authentication only.
- Issue opened, edited, closed, and reopened.
- Comment created and edited.
- Webhook-first delivery with polling backfill.
- Immutable version observations.
- Signed-delivery verification for webhooks.
- Sensitive-data and schema failures quarantine without cursor advancement.
- Transport, 429, and 5xx failures retry without cursor advancement.
- Terminal 4xx outcomes are recorded.
- No Bot lifecycle authority is emitted.
