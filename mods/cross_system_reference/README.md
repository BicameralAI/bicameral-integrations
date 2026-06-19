# Cross-System Reference Mod

Status: Built (FX-MOD) — `CrossSystemReferenceMod` in [`connector.py`](connector.py), run via
`mods.contract.run_mod`.

Advisory mod for surfacing cross-system linkage in connector evidence — when an emission's evidence
text references an external system OTHER than its own `source_id` (e.g. a Linear item whose body
links a github.com PR) — so a reviewer can reconcile the two systems before a change lands. Advisory
only: it annotates and routes; it never blocks or approves (see the
[mod safety contract](../README.md)).

## How it works

Pure, read-only function over `list[AdapterEmission]`, deterministic and stdlib-only. For each
emission it scans `title` + `body` + evidence excerpts (lowercased) against a system→markers map
(`github`→`github.com`/`gh-`, `gitlab`→`gitlab.com`, `linear`→`linear.app`, `jira`→`atlassian.net`/
`jira`, `notion`→`notion.so`, `slack`→`slack.com`/`@slack`, `sentry`→`sentry.io`,
`pagerduty`→`pagerduty.com`/`pagerduty`, `zendesk`→`zendesk.com`/`zendesk`, `confluence`) using
`mods._signals.matched_terms` (word-boundary for alnum markers, substring for punctuated ones). It
collects the foreign systems whose markers matched AND whose name is not the emission's own
`source_id` (`safe_id`-normalized) — a self-reference (a github emission mentioning github.com) is
skipped. With ≥1 foreign system it emits; otherwise no output. The foreign systems are carried in
metadata as a joined string only (no numeric score keys — forbidden).

## Outputs (mirror [`manifest.yaml`](manifest.yaml))

- `source_evidence_annotation`
- `suggested_review_question`
- `routing_hint`

## Boundary (EM-safe)

Advisory, non-authoritative (ADR-0007/0008). The mod never writes a canonical decision, approves
signoff, resolves compliance, creates a blocking CI result, bypasses policy, mutates source
evidence, or collapses a confidence score — none are representable, and `run_mod` re-screens both
the input and every wire-bound output field (FX-SEC-001). It surfaces a *reference* for a human to
reconcile; it is never a finding-of-record.

## References

See [references.md](references.md).
