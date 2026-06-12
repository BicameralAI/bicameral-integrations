<!-- GENERATED from config.json — do not edit; run scripts/build_mod_setup.py -->
# Code Review Risk — mod setup

Advisory mod that flags pR-level review risk — the first mod family behind the Bicameral Review Bot (ADR-0011).

- **id** `code_review_risk` · **manifest** `code-review-risk` · **family** review-risk · **version** 0.1.0
- **advisory only** (non-authoritative; ADR-0008) · **default enabled** True · **trust-gated** False

See [mods/README.md](README.md) for the general mod model + the mod safety contract.

## Advises on

PR-level review risk — the first mod family behind the Bicameral Review Bot (ADR-0011).

## Reads (evidence consumed)

- pull-request evidence (title + body)
- changed file paths
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
python -m runtime.cli run-mods <connector> --mods code_review_risk
```

Operator knobs:
_No operator knobs — enable/disable only._

## Requirements

- The neutral evidence stream (AdapterEmission) — no credentials, no live network.

## References

- scope: mods/code_review_risk/README.md
- mod-safety-contract: mods/README.md
- adr: docs/adr/0011-bicameral-review-bot.md
- adr: docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md
