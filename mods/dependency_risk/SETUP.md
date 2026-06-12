<!-- GENERATED from config.json — do not edit; run scripts/build_mod_setup.py -->
# Dependency Risk — mod setup

Advisory mod that flags dependency-risk signals from connector evidence — known vulnerabilities and dependency-manifest changes.

- **id** `dependency_risk` · **manifest** `dependency-risk` · **family** dependency · **version** 0.1.0
- **advisory only** (non-authoritative; ADR-0008) · **default enabled** True · **trust-gated** False

See [mods/README.md](README.md) for the general mod model + the mod safety contract.

## Advises on

Dependency-risk signals from connector evidence — known vulnerabilities and dependency-manifest changes.

## Reads (evidence consumed)

- evidence excerpt (dependency manifests, vuln mentions)
- source_ref

## Emits (advisory artifacts only)

- `dependency_signal`
- `routing_hint`
- `source_evidence_annotation`

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
python -m runtime.cli run-mods <connector> --mods dependency_risk
```

Operator knobs:
_No operator knobs — enable/disable only._

## Requirements

- The neutral evidence stream (AdapterEmission) — no credentials, no live network.

## References

- scope: mods/dependency_risk/README.md
- mod-safety-contract: mods/README.md
- adr: docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md
