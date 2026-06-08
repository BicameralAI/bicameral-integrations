# Authority Boundary Mod

Status: Scoped

Advisory mod for detecting changes that may cross Bicameral's authority,
trust-tier, or canonical-state boundaries.

## Scope

- Connectors, mods, UI, CLI, or gateway code that writes canonical decisions.
- Silent approval, signoff, compliance resolution, merge, deploy, or deletion.
- GitHub proposed writes that skip human review or policy.
- Credential scope expansion, broad filesystem access, shell execution, or
  production mutation.
- Review commands without actor identity, state transition checks, or audit
  evidence.

## Outputs

- `advisory_governance_result`
- `routing_hint`
- `source_evidence_annotation`
- `suggested_review_question`

## Boundary

This mod can raise an advisory risk and route review. It must not block CI or
enforce policy directly.

## References

See [references.md](references.md).
