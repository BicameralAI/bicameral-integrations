# Decision Drift Mod

Status: Scoped  ·  version 0.1.0

Advisory mod for surfacing source evidence that may conflict with a recorded decision, ADR, or trust tier, so a reviewer can confirm whether the decision record needs an update.

## How it works

Pure, read-only function over `list[AdapterEmission]` (no I/O). Unlike the PR-review family it is NOT gated to change evidence — a ticket or meeting note can imply an unrecorded/conflicting decision. Over the emission text (title + body + evidence excerpts, lowercased) it requires BOTH a decision anchor AND a conflict cue (`matched_terms`):

- **decision anchor** (`_DECISION_ANCHORS`) — `adr` (word-boundary, so not `quadratic`/`cadre`), `decision record`, `recorded decision`, `trust tier`, `governance decision`, `architecture decision`, `design decision`.
- **conflict cue** (`_CONFLICT_CUES`) — decision-specific phrasings: `supersede(s/d)`, `contradicts the decision`, `no longer matches`, `conflicts with the decision`, `stale decision`, `unrecorded decision`, `deviates from the decision`, `reverses the decision`, `overrides the decision`, `obsolete`, `rescinded`, `revoked`, `no longer follow(ing)`, `changed direction`, `should not follow`.

An anchor with no cue (or a cue with no anchor) → NO output (bare `overrides`/`obsolete` collide with ordinary prose).

## Outputs

- `source_evidence_annotation` — `possible decision drift on <source>: <anchors> + <cues>`.
- `advisory_governance_result` — "evidence may conflict with a recorded decision … review the decision record", metadata `{anchors, cues, source}`.
- `routing_hint` — `role="governance"`, `priority="normal"`.
- `suggested_review_question` — "Does the recorded decision need an update or a superseding ADR given this (<cues>)?"

## Boundary (EM-safe)

It suggests a decision review; it never supersedes, approves, rejects, or writes a decision record — it cannot write canonical state, approve/sign off, resolve compliance, or block CI (ADR-0007/0008/0013). Every wire-bound field is re-screened by `run_mod` (FX-SEC-001).

## References

ADR-0008 (evidence adapters, not state authorities), ADR-0013 (mod execution contract). See the [mod safety contract](../README.md) and [references.md](references.md).
