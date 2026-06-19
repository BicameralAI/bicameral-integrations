# Compliance Routing Mod

Status: Built (ADR-0013 / FX-MOD)

Advisory mod for routing evidence that **names a regulatory/compliance framework** (HIPAA,
GDPR, PCI DSS, SOC 2, CCPA, SOX, FedRAMP, NIST, ...) to a compliance reviewer — so the
regulated scope and its control obligations are weighed before a change lands. Advisory only:
it annotates and routes; it never blocks, approves, or resolves compliance (see the
[mod safety contract](../README.md)). Implemented in [`connector.py`](connector.py) as
`ComplianceRoutingMod`, run through `mods.contract.run_mod`.

## How it works

Pure, read-only function over `list[AdapterEmission]`:

- For each emission, word-boundary/substring matches a **named-framework** vocabulary
  (`hipaa`, `gdpr`, `pci`, `pci dss`, `soc 2`, `soc2`, `ccpa`, `sox`, `ferpa`, `glba`,
  `fedramp`, `iso 27001`, `nist`, `data subject`, `right to be forgotten`, `data retention`,
  `breach notification`, `regulatory`, `audit evidence`, `compliance requirement`) over
  title + body + evidence excerpts (lowercased), via `mods._signals.matched_terms` (single
  alnum tokens match whole-word; phrases match as substrings).
- On >=1 match, emits an `advisory_governance_result` naming the framework(s) (with
  `metadata` `frameworks` + `source`, no numeric score), a `routing_hint` to `compliance`
  (`priority="high"`), and a `suggested_review_question` asking whether the named obligation
  has a documented control owner and evidence trail for the change.
- No framework term -> no output.

## Boundary vs. `data_classification`

`data_classification` owns confidentiality **markers** (confidential / internal-only / nda)
and `[redacted]` PII placeholders — the sensitivity TIER of the data. This mod owns NAMED
REGULATORY FRAMEWORKS — the compliance OBLIGATION. The vocabularies are disjoint, so a change
that names only a confidentiality marker (e.g. "internal-only") does not fire here, and a
framework name (e.g. "HIPAA") does not fire `data_classification`.

## Outputs (mirror [`manifest.yaml`](manifest.yaml))

- `advisory_governance_result`
- `routing_hint`
- `suggested_review_question`

## References

See [references.md](references.md).
