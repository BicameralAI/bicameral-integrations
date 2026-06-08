# Test Adequacy Mod

Status: Scoped

Advisory mod for detecting missing or weak tests around changed behavior,
connector parsing, fixtures, governance gates, and review workflows.

## Scope

- Behavior changes without nearby tests.
- Connector parse changes without fixture coverage.
- Schema or contract changes without normalization tests.
- Governance or CI changes without focused gate tests.
- Test changes that do not exercise the risky behavior they claim to cover.

## Outputs

- `advisory_governance_result`
- `routing_hint`
- `source_evidence_annotation`
- `suggested_review_question`

## Boundary

This mod may identify test gaps and ask review questions. It must not mark a PR
as blocking or sufficient on its own.

## References

See [references.md](references.md).
