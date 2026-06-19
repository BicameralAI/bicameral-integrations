<!-- GENERATED from config.json — do not edit; run scripts/build_mod_setup.py -->
# Cross-System Reference — mod setup

Advisory mod that surfaces when an emission's evidence text references a different external system (github/gitlab/linear/jira/notion/slack/sentry/pagerduty/zendesk/confluence) than its own source_id, so a reviewer can reconcile the two systems.

- **id** `cross_system_reference` · **manifest** `cross-system-reference` · **family** integration · **version** 0.1.0 · **channel** beta
- **advisory only** (non-authoritative; ADR-0008) · **default enabled** True · **trust-gated** False

See [mods/README.md](README.md) for the general mod model + the mod safety contract.

## Advises on

Cross-system linkage: evidence text (title + body + excerpts) that names an external system other than the emission's own source_id.

## Reads (evidence consumed)

- title + body
- evidence excerpts

## Emits (advisory artifacts only)

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
python -m runtime.cli run-mods <connector> --mods cross_system_reference
```

Operator knobs:
_No operator knobs — enable/disable only._

## Requirements

- The neutral evidence stream (AdapterEmission) — no credentials, no live network.

## References

- scope: mods/cross_system_reference/README.md
- mod-safety-contract: mods/README.md
- adr: docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md
