# GitHub Incremental Issue Ingest

## Scope

This implementation belongs entirely to `bicameral-integrations`.

The first alpha slice ingests GitHub issues and comments incrementally through the shared adapter runtime and `GatewaySink` boundary. GitHub is the reference provider, not a special-case architecture.

## Executable lifecycle trace

The recorded ingress tests emit a phase model through `runtime.ingest_conformance.trace_ingest`:

```text
sanitized provider capture
  -> provider-neutral Observation
  -> validated AdapterEmission
  -> authority-stripped ExternalIngestEnvelope
  -> delivery and cursor state
```

Every phase contains:

- concrete data at that phase;
- the function that produced it;
- fields preserved;
- fields added;
- fields removed;
- the relevant hard gate;
- a compact display representation for Mermaid rendering.

`render_mermaid_trace` turns the same executable trace into a data-bearing Mermaid flowchart. The visual description and the tested runtime output therefore share one source.

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

## Mandatory mapping path

Each provider payload is parsed into a provider-neutral `Observation` with a stable `SourceRef`, bounded text, immutable evidence identity, provider event and resource identities, source-version metadata, and GitHub-specific advisory signals.

```text
GitHub payload
  -> parse_webhook_observation
  -> Observation
  -> adapter.core.pipeline.normalize
  -> universal heuristic evaluation
  -> validated AdapterEmission
  -> emission_to_external_envelope
  -> ExternalIngestEnvelope
```

The existing `emission_to_external_envelope` mapping remains the only Bot handoff.

## Fail-open heuristics

GitHub-specific logic may add advisory signals for bot authorship, dependency automation, templates, and status-only content. The universal evaluator may add provider-independent advisories.

No heuristic removes valid screened evidence. The recorded false-positive fixture proves that a bot-authored comment containing a real architecture decision remains intact through provider capture, Observation, AdapterEmission, and wire envelope.

## Cursor protocol

```text
fetch webhook or polling batch
  -> verify and parse
  -> universal normalize and screen
  -> emit through GatewaySink
  -> exact-match Bot protocol/schema/fingerprint capability check
  -> require HTTP 201
  -> persist proposed cursor
```

A crash after HTTP 201 and before cursor persistence may redeliver the same observation. Bot-side deduplication is expected. Integrations preserves deterministic provider event and resource identifiers so replay is observable and safe.

## Visible wire transformation

The current v2 envelope preserves source content, source URI, evidence excerpts, advisory labels, and provider labels. It drops Integrations evidence identity, evidence metadata, source-version metadata, author, timestamp, adapter version, connector metadata, and dimensional confidence.

That loss is recorded explicitly in the phase trace. Bot cannot claim to preserve a field it never receives.

## Alpha acceptance

- GitHub App installation authentication only.
- Issue opened, edited, closed, and reopened.
- Comment created, edited, and deleted tombstones.
- Webhook-first delivery with polling backfill.
- Immutable source versions.
- Signed-delivery verification for webhooks.
- Sensitive-data and schema failures quarantine without cursor advancement.
- Protocol version, schema digest, and contract fingerprint skew quarantine
  without delivery or cursor advancement.
- Transport, 429, and 5xx failures retry without cursor advancement.
- Terminal client outcomes follow typed cursor policy.
- No Bot lifecycle authority is emitted.
- Recorded data is visible at every Integrations phase.

## Evidence status

Implemented and component tested:

- signed recorded payload through cursor persistence;
- exact golden output;
- shared universal normalizer;
- integration and universal advisories;
- false-positive evidence preservation;
- data-bearing phase trace;
- Mermaid trace rendering;
- GitHub and Linear consumers of the same universal path.

Still required:

- sanitized real-provider provenance classification;
- Factory alpha ingest manifest;
- live production `GatewaySink` receipt;
- Bot durable evidence append;
- restart and replay;
- human acceptance.
