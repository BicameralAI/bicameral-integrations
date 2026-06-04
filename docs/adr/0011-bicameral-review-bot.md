# ADR-0011: Bicameral Review Bot

Status: Proposed
Date: 2026-06-04
Owner: BicameralAI

## Context

Bicameral needs a way to keep reviewing pull requests when an external AI review
service is unavailable, rate-limited, too expensive, or misaligned with the
project's governance model.

The near-term need is operational: maintain PR review quality without depending
on CodeRabbit review availability. The strategic opportunity is larger:
Bicameral already has provider-facing connectors, a universal adapter contract,
EM-safe mods, trust tiers, reusable CI gates, SARIF ingestion, and governance
artifacts. A Bicameral-native reviewer can use those sources as evidence instead
of treating code review as a generic diff-commenting task.

This ADR belongs in `bicameral-integrations` because the first durable boundary
is adapter/mod output: evidence collection, advisory findings, review routing,
and proposed GitHub writes. `bicameral-bot` may later enforce policy or execute
approved writes, but the integration contract and trust-tier posture are defined
here.

## Decision

Bicameral will support a first-party PR review capability named Bicameral Review
Bot.

The initial capability is an evidence-first, locally runnable PR review workflow
that produces structured advisory findings and a markdown review report. It may
be invoked by a developer, CI job, or future bot workflow without requiring
CodeRabbit.

The first implementation target is:

- collect PR evidence from git diff, changed files, test output, CI gate output,
  SARIF, dependency/security scans, connector observations, ADRs, and relevant
  governance docs;
- run deterministic checks before model review so AI findings do not duplicate
  lint, type, test, or secret-scan output;
- generate structured findings with severity, confidence, file/line evidence,
  rationale, proposed remediation, and residual risk;
- keep all findings advisory unless governance policy promotes them;
- emit draft GitHub PR comments only as proposed actions, not direct writes;
- preserve accepted, rejected, and false-positive review history as local
  learning evidence for future reviews.

## Boundary

Bicameral Review Bot is not a canonical authority.

It may:

- summarize PR intent and risk;
- identify likely correctness, security, governance, testing, documentation, and
  integration-boundary issues;
- propose review comments;
- propose follow-up tasks;
- route findings to human review;
- preserve evidence and review provenance.

It must not:

- approve pull requests;
- merge pull requests;
- dismiss human review requirements;
- mark compliance resolved;
- write canonical decisions;
- post external comments unless an explicit governed-write policy allows it;
- convert model confidence into one opaque pass/fail score;
- hide uncertainty, missing context, or unvalidated assumptions.

## Trust Tier Mapping

The capability uses separate trust tiers by operation:

| Operation | Tier | Posture |
|---|---:|---|
| Local git diff and static artifact review | T0 | Allowed with validation |
| GitHub PR metadata/read API fetch | T1 | Allowed with scoped credentials |
| GitHub webhook-triggered review ingest | T2 | Requires signature validation and replay protection |
| Draft GitHub PR comments | T3 | Proposed write; human review required |
| Posting GitHub PR comments | T4 | Governed write; requires explicit policy |
| Merge, branch deletion, credential expansion, or broad agent execution | T5 | Denied unless separately approved |

## Finding Schema

Every review finding must preserve enough evidence to be independently assessed.

Required fields:

- `finding_id`
- `source`
- `category`
- `severity`
- `confidence`
- `file`
- `line` or `range`
- `title`
- `rationale`
- `evidence`
- `suggested_fix`
- `residual_risk`
- `reviewer_version`

Findings without concrete file, line, or source evidence must be labeled as
questions or risks, not defects.

## Review Passes

The default review bundle includes separate passes:

- correctness and behavior regression;
- security and secret handling;
- authority boundary and trust-tier drift;
- adapter/connector contract preservation;
- test adequacy;
- documentation and ADR drift;
- dependency and supply-chain risk;
- maintainability only when it affects behavior, risk, or operability.

Style-only comments are suppressed unless the repository has an explicit style
rule and no deterministic tool already reports it.

## CodeRabbit Independence

CodeRabbit may remain useful as an external reviewer, but Bicameral review
quality must not depend on CodeRabbit availability or rate limits.

When external review is unavailable, the Bicameral workflow should still provide:

- PR summary;
- risk-ranked findings;
- deterministic gate context;
- security and governance checks;
- review questions for humans;
- suggested remediation;
- artifacted report output suitable for CI or PR discussion.

## Consequences

### Positive

- PR review can continue when external AI review limits are exhausted.
- Review output can use Bicameral-specific governance and trust-tier context.
- Findings become auditable evidence rather than transient chat comments.
- The system can learn from accepted and rejected local findings.
- GitHub write authority remains explicitly staged instead of implicit.

### Negative

- A local reviewer requires model/API configuration or a supported local model.
- Poor prompt or context-pack design can still create false positives.
- CI runtime and token cost may rise for large PRs.
- Posting comments later requires a T4 policy and audit trail.

## Implementation Plan

1. Add an EM-safe `mods/code_review` package with a manifest, fixture inputs,
   expected finding output, and forbidden actions.
2. Add a local CLI entry point that compares the current branch to a base ref
   and writes a markdown report plus structured JSON findings.
3. Feed deterministic gate outputs into the review context before any model
   pass.
4. Add tests for finding schema validation, false-positive memory handling, and
   trust-tier enforcement.
5. Add an optional GitHub proposed-comment exporter that emits T3 proposed
   actions without posting.
6. Move to T4 GitHub comment posting only after a separate governed-write policy
   is approved.

## Acceptance Criteria

This ADR is implemented when:

- developers can run a local review against a PR branch without CodeRabbit;
- review output includes structured findings and a markdown report;
- all findings preserve source evidence and reviewer provenance;
- false positives can be recorded and used as future review context;
- GitHub comments are draft/proposed actions unless T4 policy is present;
- CI can artifact review output without making the AI reviewer a blocking
  authority by default.
