# RFQ Addendum: GitHub Source Acquisition for Alpha Decision Candidates

Date: 2026-07-16
Status: open for Kevin Knapp and Jin Kuan review
Owner: Bicameral Integrations
Related: `docs/rfq-bot-integrations-boundary-2026-06-06.md`, ADR-0017 provider acquisition contract, Bot merged PR #325

## Purpose

Define the integrations-side contract for GitHub issues as Bicameral's first alpha dogfooding source. This document extends the existing bot/integrations boundary RFQ without changing its authority split.

Integrations owns provider acquisition, verification, source normalization, producer-side screening, and replay-safe delivery. Bot owns evidence acceptance, SourceSnapshot materialization, filtration policy, reasoning projection, candidate convergence, weighting, lifecycle, review routing, and persistent Decisions.

## Fixed boundary

Integrations may send:

- screened source facts;
- evidence excerpts or approved source content;
- stable provider references;
- delivery and verification provenance;
- advisory hints.

Integrations must not send or claim:

- accepted Decisions;
- authoritative DecisionCandidates;
- decision level or authority;
- ratification or review outcomes;
- bot ActorContext;
- persistent-memory mutation;
- final relevance score;
- lifecycle promotion.

## RFQ A: GitHub issue acquisition scope

### Initial events

Evaluate support for:

- issue opened;
- issue edited;
- issue closed or reopened;
- issue comment created or edited;
- label and milestone changes;
- assignee changes;
- cross-reference and linked pull-request events.

### Decision requested

Choose the minimum alpha event set. The recommendation is issue body plus comments and state transitions, with low-value administrative events retained as metadata rather than independent observations.

## RFQ B: Normalized source envelope

The GitHub adapter should produce a provider-neutral observation containing at least:

- provider: `github`;
- repository stable identifier and full name;
- issue number and node identifier;
- canonical URL;
- issue state;
- title and body;
- author identifier and type;
- created, updated, and closed timestamps;
- labels, milestone, assignees, and linked pull requests where available;
- comment identifier, author, timestamp, and body for comment observations;
- delivery identifier and event type;
- delivery mode and signature-verification result;
- source version or content hash;
- connector and schema version.

### Decision requested

Confirm which fields cross the wire as source facts, which remain connector-local metadata, and whether full bodies or bounded excerpts are sent for alpha.

## RFQ C: Producer-side screening and exclusion hints

Integrations performs deterministic producer-side checks before delivery:

- signature or credential verification;
- schema and payload-size validation;
- secret, credential, PHI, PAN, and configured sensitive-data screening;
- unsupported repository or workspace exclusion;
- replay and delivery deduplication;
- malformed encoding or binary-content rejection.

Integrations may attach advisory hints for obvious provider boilerplate, bot-generated comments, synchronization events, or administratively generated noise. These hints must not become authoritative Bot exclusions.

### Decision requested

Choose the alpha handling for bot-authored GitHub content, automated dependency notices, status-only comments, and issue templates with little user content. Confirm whether integrations drops them, downgrades them to evidence-only, or forwards them with noise hints.

## RFQ D: Delivery, retry, and cursor semantics

GitHub webhook delivery should preserve at-least-once semantics. Bot deduplication must make replay effectively once at canonical materialization.

Required outcomes:

- accepted: advance delivery state;
- terminal schema or policy rejection: record terminal outcome and surface for review;
- rate limit, transport, or server error: retry without advancing;
- sensitive-data rejection: quarantine and alert;
- contract drift: fail the contract gate and do not silently skip.

### Decision requested

Confirm webhook-first alpha posture, whether any polling backfill is required, retry limits, dead-letter handling, and the durable receipt shape returned by Bot.

## RFQ E: Update and deletion semantics

GitHub issues and comments can be edited or deleted after initial capture.

Integrations should emit new immutable observations referencing the same provider object and a new content version. It should not rewrite Bot evidence history.

### Decision requested

Choose the alpha policy for:

- edited issue bodies;
- edited comments;
- deleted comments;
- transferred issues;
- renamed repositories;
- inaccessible private repositories;
- force-deleted or redacted source content.

The recommended posture is immutable observation history plus a current-source availability marker, with security-driven redaction handled through an explicit governed removal process rather than ordinary connector updates.

## RFQ F: Alpha conformance fixtures

The integration package must provide fixtures for:

- clear product decision discussion;
- ambiguous question with no decision;
- high-volume issue with mixed signal;
- bot-generated or templated noise;
- edited issue and comment;
- duplicate webhook delivery;
- signature failure;
- sensitive-data rejection;
- rate-limit and retry;
- repository rename or transfer.

Each fixture must validate normalized output, screening outcome, provenance, idempotency key, and expected Bot handoff lane.

## Cross-repository acceptance criteria

- GitHub-specific logic terminates at the neutral acquisition envelope.
- Bot can change filtration or weighting policy without reconfiguring the GitHub connector.
- Source provenance remains sufficient to reconstruct what GitHub object and version produced each evidence record.
- Integrations never assigns final candidate relevance or lifecycle state.
- Delivery is replay-safe and contract-versioned.
- Security and schema failures are explicit, observable, and non-silent.
- The contract supports independent integration fixtures before end-to-end alpha evaluation.

## Requested decisions

Kevin and Jin should record:

- minimum GitHub event scope;
- full-body versus excerpt policy;
- bot-generated-content handling;
- webhook and optional backfill posture;
- edit and deletion behavior;
- receipt and retry contract;
- schema version targeted for alpha.
