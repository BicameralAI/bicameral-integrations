# Notification Scope Risk Mod

Status: Built (ADR-0013)

Advisory mod for surfacing broad/unscoped broadcast-notification language from connector
evidence — `@channel`, `notify all`, `company-wide`, `all-hands`, and similar — so a reviewer
can check the *blast radius* of a notification before it ships. Advisory only: it annotates,
asks, and routes; it never blocks or approves (see the [mod safety contract](../README.md)).
Implemented in [`connector.py`](connector.py) as `NotificationScopeRiskMod`, run through
`mods.contract.run_mod`.

## How it works

Pure, read-only function over `list[AdapterEmission]`, one deterministic path:

- **Broadcast-scope path** — over each emission's title + body + evidence excerpts
  (lowercased), match the over-broad broadcast vocabulary via the shared
  [`matched_terms`](../_signals.py) matcher. The terms are phrases or carry `@`/`-`, so they
  are substring-matched; the bare token `broadcast` is intentionally excluded as too broad to
  signal over-scope on its own. When `>= 1` term matches, emit (using `safe_id(source_id)`):
  an `advisory_governance_result` naming the matched signals (metadata `signals` + `source`,
  no numeric score), a `routing_hint` to `security`, and a `suggested_review_question` asking
  whether the notification is scoped to the necessary recipients. No match emits nothing.

## Outputs (mirror [`manifest.yaml`](manifest.yaml))

- `advisory_governance_result`
- `routing_hint`
- `suggested_review_question`

## References

See the [mod safety contract](../README.md) and
[ADR-0008](../../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md).
