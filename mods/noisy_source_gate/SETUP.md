<!-- GENERATED from config.json — do not edit; run scripts/build_mod_setup.py -->
# Noisy Source Gate — mod setup

Advisory mod that recommends manual review-gating for high-noise evidence sources unless the operator has raised the source's trust.

- **id** `noisy_source_gate` · **manifest** `noisy-source-gate` · **family** trust · **version** 0.1.0
- **advisory only** (non-authoritative; ADR-0008) · **default enabled** True · **trust-gated** True

See [mods/README.md](README.md) for the general mod model + the mod safety contract.

## Advises on

High-volume, low-signal channels (Slack chat, Granola/Fathom meeting transcripts) flooding the candidate store; recommends a manual gate unless the source's trust tier is operator-raised. A non-noisy source yields nothing.

## Reads (evidence consumed)

- source_id
- operator source-trust configuration (read-only)

## Emits (advisory artifacts only)

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
python -m runtime.cli run-mods <connector> --mods noisy_source_gate
```

Operator knobs:

| key | required | default | description |
|---|---|---|---|
| `raised_trust_sources` | False | — | Source ids the operator has explicitly trusted, so the mod does NOT recommend a manual gate for them. The default high-noise set (slack/granola/fathom) is config-as-code in the mod. |

## Requirements

- The neutral evidence stream (AdapterEmission) — no credentials, no live network.
- Optional: an operator source-trust map to suppress the gate for raised sources.

## References

- scope: mods/noisy_source_gate/README.md
- mod-safety-contract: mods/README.md
- adr: docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md
