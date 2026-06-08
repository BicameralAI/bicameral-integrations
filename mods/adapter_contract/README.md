# Adapter Contract Mod

Status: Scoped

Advisory mod for detecting evidence-shape and contract-preservation risks in
connector and adapter output.

## Scope

- Missing or unstable `source_ref` fields.
- Lost provider-native ids, timestamps, URLs, excerpts, or evidence pointers.
- Output that bypasses `Observation` to `AdapterEmission` normalization.
- Schema or SARIF fields that cannot be independently reviewed.
- Connector behavior that starts owning canonical state.

## Outputs

- `source_evidence_annotation`
- `routing_hint`
- `advisory_governance_result`

## Boundary

This mod may annotate contract risk and suggest review questions. It must not
accept, reject, mutate, or repair canonical records.

## References

See [references.md](references.md).
