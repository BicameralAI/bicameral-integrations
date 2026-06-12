<!-- GENERATED from config.json — do not edit; run scripts/build_mod_setup.py -->
# Decision Drift — mod setup

Advisory mod that flags new source evidence that appears to conflict with recorded decisions, ADRs, trust tiers, or governance docs.

- **id** `decision_drift` · **manifest** `decision-drift` · **family** governance-boundary · **version** 0.1.0 · **channel** beta
- **advisory only** (non-authoritative; ADR-0008) · **default enabled** True · **trust-gated** False

See [mods/README.md](README.md) for the general mod model + the mod safety contract.

## Advises on

New source evidence that appears to conflict with recorded decisions, ADRs, trust tiers, or governance docs.

## Reads (evidence consumed)

- evidence excerpt + title
- source_ref
- recorded decisions/ADRs (read-only)

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
python -m runtime.cli run-mods <connector> --mods decision_drift
```

Operator knobs:
_No operator knobs — enable/disable only._

## Requirements

- The neutral evidence stream (AdapterEmission) — no credentials, no live network.

## References

- scope: mods/decision_drift/README.md
- mod-safety-contract: mods/README.md
- adr: docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md
