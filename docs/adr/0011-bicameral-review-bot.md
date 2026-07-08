# ADR-0011: Bicameral Review Bot — PR Evidence Pack

Status: Proposed (amended 2026-06-24)
Date: 2026-06-04
Amended: 2026-06-24
Owner: BicameralAI
Relates to: ADR-0017 (the discovery edge's `create_provider_resource` reuses the ProposedAction lane)
Links: #42, PR #69

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

### Amendment context (2026-06-24)

The original ADR scoped a generic "AI code review" capability. Experience with
the `mods/code_review_risk` implementation and the bot-side preflight system
(see `bicameral-bot` `preflight.run`) shows the integrations boundary is better
framed as **PR preflight/review evidence packaging**: integrations collect,
normalize, and package evidence items and advisory hints that the bot consumes
for its own preflight interpretation. The bot owns the preflight execution
boundary; integrations supply the evidence pack and advisory mod outputs that
feed it.

This amendment adds:

- A shared protocol shape for evidence items and advisory hints.
- Bot-owned `preflight.run` as a boundary reference (not reimplemented here).
- Review-question candidates modeled as advisory/review-lane input.
- PR comment drafts modeled as T3 proposed actions (not direct publish).
- Mod advisory output scope limited to governance/integration-boundary evidence
  and hints — deterministic lint/type/test checks are not duplicated.

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

### PR Evidence Pack (amended)

The review capability's primary output toward the bot is a **PR Evidence Pack**:
a typed collection of evidence items and advisory hints packaged for bot-side
preflight consumption. The pack is the integration boundary's deliverable; the
bot interprets, enforces, and acts on its contents.

#### Shared protocol shape

Evidence items and hints share a minimal protocol shape that both integrations
and bot can depend on without tight coupling:

```python
@dataclass(frozen=True)
class EvidenceItem:
    """One piece of PR-scoped evidence collected by integrations."""
    item_id: str
    source: str          # connector or mod that produced this item
    kind: str            # e.g. "diff_context", "ci_gate_result", "sarif_finding"
    summary: str
    evidence_ref: str    # stable reference (file:line, URL, SARIF location)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdvisoryHint:
    """An advisory observation produced by a mod for bot-side interpretation."""
    hint_id: str
    source_mod: str      # mod id that produced this hint
    category: str        # e.g. "governance_boundary", "integration_contract"
    message: str
    severity: str        # "info" | "low" | "medium" | "high"
    evidence_item_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReviewQuestionCandidate:
    """A question surfaced by a mod for human review consideration.

    Advisory input only — not a draft outbound write or canonical decision.
    The bot's review lane may present, suppress, or reframe these.
    """
    question_id: str
    source_mod: str
    question: str
    context_item_ids: tuple[str, ...] = ()
    priority: str = "normal"  # "low" | "normal" | "high"


@dataclass(frozen=True)
class PRCommentDraft:
    """A proposed PR comment — T3 proposed action, never directly published.

    The bot decides whether to present, approve, or discard. Integrations
    never post comments; the draft is advisory evidence for the bot's
    governed-write pipeline.
    """
    draft_id: str
    source_mod: str
    file: str
    line: int | None = None
    body: str = ""
    comment_type: str = "inline"  # "inline" | "top_level"
    linked_finding_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class PREvidencePack:
    """The integrations-side deliverable consumed by bot preflight."""
    pr_ref: str          # e.g. "owner/repo#123"
    evidence_items: tuple[EvidenceItem, ...] = ()
    advisory_hints: tuple[AdvisoryHint, ...] = ()
    review_questions: tuple[ReviewQuestionCandidate, ...] = ()
    comment_drafts: tuple[PRCommentDraft, ...] = ()
    deterministic_results_ref: str = ""  # reference to CI/lint/test results
```

#### Bot-owned preflight.run boundary

The bot's `preflight.run` is the execution boundary that interprets and acts on
the evidence pack. Integrations **reference** this boundary but do not
reimplement its semantics:

- Integrations produce `PREvidencePack` instances.
- Bot's `preflight.run` consumes the pack, applies policy, and decides actions.
- Integrations never execute preflight logic, enforce policy, or decide whether
  a PR passes or fails.
- The `deterministic_results_ref` field references lint/type/test/secret-scan
  outputs so that bot can correlate them without integrations duplicating those
  checks.

#### Review-question candidates as advisory input

`ReviewQuestionCandidate` is modeled as **advisory/review-lane input**, not as a
draft outbound write or canonical decision:

- A mod surfaces questions it cannot answer from static evidence alone.
- The bot's review lane receives these as candidates and decides presentation.
- Questions never become governance state, canonical decisions, or published
  comments without bot-side approval.
- The existing `suggested_review_question` mod output kind maps to this shape.

#### PR comment draft as T3 proposed action

`PRCommentDraft` is a T3 proposed write (Trust Tier table row 4):

- Integrations produce draft comments with file/line anchors and linked findings.
- The draft is **never posted directly** by integrations.
- Bot receives drafts and may approve, edit, batch, suppress, or discard them
  according to its governed-write policy.
- T4 (actual posting) requires a separate governed-write policy (unchanged from
  original ADR).

#### Mod advisory scope: governance/integration-boundary evidence

Mod advisory output in the evidence-pack context is scoped to
governance/integration-boundary evidence and hints:

- Authority boundary drift (does the PR move trust-tier boundaries?).
- Integration contract preservation (does the PR break adapter/emission shape?).
- Governance artifact changes (ADR, ledger, policy doc modifications).
- Supply-chain and dependency-governance risk.

Mods **do not** duplicate deterministic lint, type-check, test, or secret-scan
results. Those results are referenced via `deterministic_results_ref` so the bot
can correlate them without re-running or re-interpreting them in the mod layer.

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

### Amended plan additions (2026-06-24)

7. Define `protocol/pr_evidence_pack/` with the shared protocol shapes above
   (stdlib-only, frozen dataclasses).
8. Wire `mods/code_review_risk` output into `AdvisoryHint` / `ReviewQuestionCandidate`
   shape when producing a `PREvidencePack`.
9. Add `PRCommentDraft` assembly from existing finding schema (T3 proposed
   action; no T4 posting).
10. Validate that `deterministic_results_ref` is populated and that mod advisory
    output does not re-run deterministic checks.
11. Add integration tests verifying the evidence-pack round-trip with a mock
    bot consumer.

## Acceptance Criteria

This ADR is implemented when:

- developers can run a local review against a PR branch without CodeRabbit;
- review output includes structured findings and a markdown report;
- all findings preserve source evidence and reviewer provenance;
- false positives can be recorded and used as future review context;
- GitHub comments are draft/proposed actions unless T4 policy is present;
- CI can artifact review output without making the AI reviewer a blocking
  authority by default.

### Amended acceptance criteria (2026-06-24)

- `PREvidencePack` protocol shape is defined and importable.
- Bot-owned `preflight.run` is referenced as the consumer; integrations do not
  reimplement preflight semantics.
- `ReviewQuestionCandidate` is advisory input to the review lane, not a draft
  outbound write.
- `PRCommentDraft` is a T3 proposed action; no direct-publish path exists in
  integrations.
- Mod advisory output is scoped to governance/integration-boundary evidence;
  deterministic checks are referenced, not duplicated.
