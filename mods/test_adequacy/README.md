# Test Adequacy Mod

Status: Scoped  ·  version 0.1.0

Advisory mod for surfacing a behavior change whose text names no test, so a reviewer can ask for the missing coverage before merge.

## How it works

Pure, read-only function over `list[AdapterEmission]`, fires only on **change evidence** (`is_change_evidence` — a `pull_request` / `issue` / `merge_request`) and keys off the change text (title + body + evidence excerpts, lowercased):

- **behavior change without test signal** — the text hits a `_BEHAVIOR_TERMS` marker (via `matched_terms`) AND no `_TEST_TERMS` marker (via `any_match`):
  - behavior markers: `fix(es/ed)` (word-boundary, so not `prefix`), `bug(s)`, `feature`, `refactor(ed)`, `migration(s)`, `endpoint`, `parser`, `handler`, `validation`, `logic`, `regression`, `behavior`, `patch(ed)`, `rewrite`/`rewrote`, `optimize(d)`, `implement`, `hotfix`.
  - test markers (any one suppresses the signal): `test(s/ed/ing)` (word-boundary, so not `latest`/`contest`), `spec(s)`, `fixture(s)`, `coverage`, `assert(s)`, `pytest`, `unit test`.

A change that already references tests, or that is not a behavior change, or non-change evidence → NO output.

## Outputs

- `source_evidence_annotation` — `behavior change on <source> (<terms>) with no test signal in the text`.
- `advisory_governance_result` — "possible test gap — behavior change … names no test/fixture", metadata `{behavior, source}`.
- `routing_hint` — `role="review"`, `priority="normal"`.
- `suggested_review_question` — "Does this <terms> change add or update a test that exercises the new behavior?"

## Boundary (EM-safe)

It identifies a possible test gap and asks a review question; it never marks a PR blocking or sufficient — it cannot write canonical state, approve/sign off, resolve compliance, or create a blocking CI result (ADR-0007/0008/0013). Every wire-bound field is re-screened by `run_mod` (FX-SEC-001).

## References

ADR-0008 (evidence adapters, not state authorities), ADR-0013 (mod execution contract). See the [mod safety contract](../README.md) and [references.md](references.md).
