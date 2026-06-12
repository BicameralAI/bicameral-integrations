<!-- GENERATED from config.json — do not edit; run scripts/build_mod_setup.py -->
# Adapter Contract — mod setup

Advisory mod that flags evidence-shape and contract-preservation risks in connector/adapter output.

- **id** `adapter_contract` · **manifest** `adapter-contract` · **family** evidence-contract · **version** 0.1.0 · **channel** beta
- **advisory only** (non-authoritative; ADR-0008) · **default enabled** True · **trust-gated** False

See [mods/README.md](README.md) for the general mod model + the mod safety contract.

## Advises on

Missing or unstable source_ref fields; lost provider-native ids/timestamps/URLs/excerpts/evidence pointers; output that bypasses the Observation -> AdapterEmission normalization; schema/SARIF fields that cannot be independently reviewed; connector behavior that starts owning canonical state.

## Reads (evidence consumed)

- source_ref fields (source_id, ref, url, kind)
- evidence excerpt + title
- emission shape / normalization metadata

## Emits (advisory artifacts only)

- `source_evidence_annotation`
- `routing_hint`
- `advisory_governance_result`

## Can NEVER do (EM-safe boundary)

This mod is non-authoritative by construction — it may surface a concern, never act on it:
- `write_canonical_decision`
- `approve_signoff`
- `resolve_compliance`
- `create_blocking_ci_result`
- `bypass_governance_policy`
- `mutate_source_evidence`
- `collapse_confidence_score`

## Enable it (headless — no UI)

```bash
python -m runtime.cli run-mods <connector> --mods adapter_contract
```

Operator knobs:
_No operator knobs — enable/disable only._

## Requirements

- The neutral evidence stream (AdapterEmission) — no credentials, no live network.

## References

- scope: mods/adapter_contract/README.md
- mod-safety-contract: mods/README.md
- adr: docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md
