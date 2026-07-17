# GitHub Incremental Issue Ingest for Alpha

Date: 2026-07-17
Status: Implemented for review in PR #255
Owner: Bicameral Integrations
Related: issue #256, ADR-0017 provider acquisition contract, Factory #210

## Purpose

Define and implement the integrations-side contract for GitHub issues as Bicameral's first alpha dogfooding ingest source.

Integrations owns provider acquisition, verification, source normalization, producer-side screening, cursor persistence, and replay-safe delivery. Bot owns evidence acceptance, SourceSnapshot materialization, filtration policy, reasoning projection, candidate convergence, weighting, lifecycle, review routing, and persistent Decisions.

## Accepted alpha scope

The first increment supports:

- issue opened;
- issue edited;
- issue closed or reopened;
- issue comment created or edited;
- deleted comments as content-free tombstone observations;
- webhook-first delivery;
- polling backfill from a durable per-repository cursor;
- GitHub App installation authentication only;
- bounded screened text;
- immutable source versions;
- at-least-once delivery through `GatewaySink`.

Label, milestone, assignee, and linked-pull-request changes remain metadata on the next issue observation rather than independent emissions. Pull-request, commit, repository-clone, and code-indexing ingest are deferred.

## Data flow

```text
GitHub webhook or bounded poll
  -> signature / installation-token verification
  -> GitHub source normalization
  -> immutable source version and stable provider identifiers
  -> AdapterEmission(emission_type="evidence")
  -> existing GatewaySink
  -> authority-stripped ExternalIngestEnvelope
  -> Bot external-ingest gate
```

## Stable source identity

Each observation preserves repository id and full name, issue number and id, comment id when applicable, delivery id, source kind, canonical URL, updated timestamp, deterministic content-version digest, and schema version.

Edits create new immutable observations. Integrations never rewrites Bot history.

## Screening and noise

The connector sends screened source facts and bounded excerpts. Removed content is never repeated in a tombstone. Bot-authored, dependency, templated, and status-only content is retained with advisory noise labels rather than authoritatively discarded.

## Cursor and delivery semantics

Cursor advancement is a two-phase operation:

```text
normalize -> emit -> receive HTTP 201 -> atomically persist cursor
```

- `201`: advance;
- transport, `429`, and `5xx`: retry without advancing;
- sensitive-data or schema-drift rejection: quarantine without advancing;
- terminal `4xx`: record the terminal outcome according to the existing cursor policy.

A crash after Bot acceptance but before cursor persistence may replay the source observation. Stable provider and content-version identifiers make that replay deduplicable downstream.

## Authority boundary

Integrations may emit source facts, evidence excerpts, stable provider references, delivery provenance, and advisory hints.

Integrations must not emit or claim accepted Decisions, authoritative DecisionCandidates, decision level, signoff, compliance, ActorContext, lifecycle promotion, final relevance, or event-store mutation.

## Implementation

- `protocol/provider_acquisition/github/ingest.py`
- `protocol/provider_acquisition/github/tests/test_github_ingest.py`

## Factory lifecycle metadata

```yaml
factory_lifecycle_ref: BicameralAI/bicameral-factory#210
evidence_class: implementation
journey_status_claim: none
acceptance_authority: factory
```

This implementation does not claim terminal evidence, human acceptance, or alpha readiness. A real GitHub App to Integrations to production Bot daemon journey remains required for terminal evidence.
