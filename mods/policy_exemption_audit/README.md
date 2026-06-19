# Policy Exemption Audit Mod

Status: Built (ADR-0013 / FX-MOD)

Advisory mod for surfacing evidence that **claims a policy exemption, waiver, or accepted
risk** — so the claim can be explicitly re-approved by a policy owner with an audit record and
expiry, rather than quietly persisting. Advisory only: it annotates and routes; it never blocks,
approves, or resolves compliance (see the [mod safety contract](../README.md)). Implemented in
[`connector.py`](connector.py) as `PolicyExemptionAuditMod`, run through `mods.contract.run_mod`.

## How it works

Pure, read-only function over `list[AdapterEmission]`:

- For each emission, word-boundary/substring matches an **exemption-claim** vocabulary
  (`exempt`, `exemption`, `waiver`, `waived`, `grandfathered`, `accepted risk`, `risk accepted`,
  `policy exception`, `exception granted`, `wontfix`, `won't fix`, `will not fix`,
  `suppress finding`, `suppressed finding`, `ignore rule`, `ignore finding`, `override approved`,
  `temporary exception`, `compliance exception`) over title + body + evidence excerpts
  (lowercased), via `mods._signals.matched_terms` (single alnum tokens match whole-word;
  phrases match as substrings).
- On >=1 match, emits an `advisory_governance_result` naming the claimed exemption, a
  `routing_hint` to `policy` (`priority="high"`), and a `suggested_review_question` asking
  whether the exemption has been re-approved by a policy owner with an audit record and expiry.
- No exemption term -> no output.

## Boundary vs. `authority_boundary`

`authority_boundary` owns authority-crossing **actions** (auto-merge, bypass-governance,
deploy-without-review). This mod owns exemption **claims**. The vocabularies are disjoint, so a
change that names only an authority phrase (e.g. "auto-merge enabled") does not fire here.

## Outputs (mirror [`manifest.yaml`](manifest.yaml))

- `advisory_governance_result`
- `routing_hint`
- `suggested_review_question`

## References

See [references.md](references.md).
