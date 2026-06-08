# Decision Drift Mod

Status: Scoped

Advisory mod for detecting when new source evidence appears to conflict with
recorded decisions, ADRs, trust tiers, or governance docs.

## Scope

- Code or docs that contradict an ADR or trust-tier rule.
- Connector behavior that no longer matches its documented mode or surface.
- PR descriptions, tickets, or meeting notes that imply an unrecorded decision.
- Accepted decisions that appear stale relative to implementation evidence.

## Outputs

- `advisory_governance_result`
- `routing_hint`
- `source_evidence_annotation`
- `suggested_review_question`

## Boundary

This mod may suggest decision review. It must not supersede, approve, reject, or
write decision records.

## References

See [references.md](references.md).
