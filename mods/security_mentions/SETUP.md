<!-- GENERATED from config.json — do not edit; run scripts/build_mod_setup.py -->
# Security Mentions — mod setup

Advisory mod that flags whole-word security keywords (auth/token/secret/credential/oauth/webhook/cve/...) in title + body + evidence excerpts.

- **id** `security_mentions` · **manifest** `security-mentions` · **family** security · **version** 0.1.0 · **channel** beta
- **advisory only** (non-authoritative; ADR-0008) · **default enabled** True · **trust-gated** False

See [mods/README.md](README.md) for the general mod model + the mod safety contract.

## Advises on

Whole-word security keywords (auth/token/secret/credential/oauth/webhook/cve/...) in title + body + evidence excerpts.

## Reads (evidence consumed)

- title + body
- evidence excerpts

## Emits (advisory artifacts only)

- `advisory_governance_result`
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
python -m runtime.cli run-mods <connector> --mods security_mentions
```

Operator knobs:
_No operator knobs — enable/disable only._

## Requirements

- The neutral evidence stream (AdapterEmission) — no credentials, no live network.

## References

- scope: mods/security_mentions/README.md
- mod-safety-contract: mods/README.md
- adr: docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md
