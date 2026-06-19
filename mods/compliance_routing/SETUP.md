<!-- GENERATED from config.json — do not edit; run scripts/build_mod_setup.py -->
# Compliance Routing — mod setup

Advisory mod that routes evidence naming a regulatory/compliance framework (HIPAA/GDPR/PCI DSS/SOC 2/CCPA/SOX/FedRAMP/NIST/...) to a compliance reviewer so the regulated scope is weighed before a change lands.

- **id** `compliance_routing` · **manifest** `compliance-routing` · **family** governance · **version** 0.1.0 · **channel** beta
- **advisory only** (non-authoritative; ADR-0008) · **default enabled** True · **trust-gated** False

See [mods/README.md](README.md) for the general mod model + the mod safety contract.

## Advises on

Named regulatory/compliance frameworks (HIPAA/GDPR/PCI/PCI DSS/SOC 2/CCPA/SOX/FERPA/GLBA/FedRAMP/ISO 27001/NIST/data subject/breach notification/...) in title + body + evidence excerpts.

## Reads (evidence consumed)

- title + body
- evidence excerpts

## Emits (advisory artifacts only)

- `advisory_governance_result`
- `routing_hint`
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
python -m runtime.cli run-mods <connector> --mods compliance_routing
```

Operator knobs:
_No operator knobs — enable/disable only._

## Requirements

- The neutral evidence stream (AdapterEmission) — no credentials, no live network.

## References

- scope: mods/compliance_routing/README.md
- mod-safety-contract: mods/README.md
- adr: docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md
