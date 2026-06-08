# Source Trust Calibration Mod

Status: Scoped

Advisory mod for calibrating source trust based on provenance, source type,
historical noise, data sensitivity, and operation tier.

## Scope

- Signals that a source should remain advisory, require manual review, or be
  eligible for higher-trust routing.
- Provenance quality for artifacts, PRs, scans, connector payloads, and agent
  output.
- Historical false positives, unknown schemas, missing actor identity, and weak
  evidence pointers.
- Trust-tier mismatches between source data and requested action.

## Outputs

- `advisory_governance_result`
- `routing_hint`
- `source_evidence_annotation`

## Boundary

This mod may suggest source-trust routing. It must not change canonical trust
tier configuration or promote evidence to accepted decisions.

## References

See [references.md](references.md).
