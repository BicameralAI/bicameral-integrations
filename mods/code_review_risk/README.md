# Code Review Risk Mod

Status: Scoped

Advisory mod for PR-level review risk. This is the first mod family behind the
Bicameral Review Bot direction.

## Scope

- Broad blast radius, high-risk files, migrations, auth changes, state changes,
  dependency changes, and security-sensitive paths.
- Correctness or behavior-regression questions grounded in changed code.
- Missing tests for behavior changes.
- Proposed GitHub comments as draft review output only.

## Outputs

- `advisory_governance_result`
- `routing_hint`
- `source_evidence_annotation`
- `suggested_review_question`

## Boundary

This mod may produce review findings and draft comments. It must not approve,
request changes, post GitHub comments, or merge.

## References

See [references.md](references.md).
