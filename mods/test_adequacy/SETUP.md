<!-- GENERATED from config.json — do not edit; run scripts/build_mod_setup.py -->
# Test Adequacy — mod setup

Advisory mod that flags missing or weak tests around changed behavior, connector parsing, fixtures, governance gates, and review workflows.

- **id** `test_adequacy` · **manifest** `test-adequacy` · **family** testing · **version** 0.1.0 · **channel** beta
- **advisory only** (non-authoritative; ADR-0008) · **default enabled** True · **trust-gated** False

See [mods/README.md](README.md) for the general mod model + the mod safety contract.

## Advises on

Missing or weak tests around changed behavior, connector parsing, fixtures, governance gates, and review workflows.

## Reads (evidence consumed)

- changed file paths
- evidence excerpt (tests/fixtures/gates)
- source_ref

## Emits (advisory artifacts only)

- `advisory_governance_result`
- `routing_hint`
- `source_evidence_annotation`
- `suggested_review_question`

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
python -m runtime.cli run-mods <connector> --mods test_adequacy
```

Operator knobs:
_No operator knobs — enable/disable only._

## Requirements

- The neutral evidence stream (AdapterEmission) — no credentials, no live network.

## References

- scope: mods/test_adequacy/README.md
- mod-safety-contract: mods/README.md
- adr: docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md
