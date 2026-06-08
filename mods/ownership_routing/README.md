# Ownership Routing Mod

Status: Scoped

Advisory mod for suggesting reviewer lenses and domain ownership based on
changed paths, source evidence, and recorded ownership hints.

## Scope

- CODEOWNERS and path ownership hints.
- Connector, adapter, governance, security, docs, and CI domain routing.
- Review questions for likely owners.
- Mismatches between risky changes and requested reviewers.

## Outputs

- `owner_lens_hint`
- `routing_hint`
- `source_evidence_annotation`

## Boundary

This mod may suggest reviewers or owner lenses. It must not assign reviewers,
require approval, or override branch protection.

## References

See [references.md](references.md).
