# Webhook Risk Mod

Status: Scoped  ·  version 0.1.0

Advisory mod for surfacing webhook-safety signals — a change that touches a webhook surface and names a concrete verification/replay risk — so a reviewer can confirm signature + replay protection before it lands.

## How it works

Pure, read-only function over `list[AdapterEmission]` (no I/O, NOT a parser); signals come only from the emission text (title + body + evidence excerpts, lowercased):

- **webhook context** (always annotated) — the text references a webhook surface (`any_match` over `_WEBHOOK_TERMS`): `webhook`, a provider signature header (`x-hub-signature`, `x-slack-signature`, `x-notion-signature`, `x-pagerduty-signature`), `svix`, `hmac signature`.
- **named risk** (additionally routes) — the text names a concrete risk (`matched_terms` over `_RISK_TERMS`): `replay`, `spoof`, `unverified`, `bypass signature`, `missing signature`, `no signature`, `no dedup`, `without verification`, `skip verification`, `forged`, `no replay`, `without dedup`, `no verification`, `tampered`, `signature not checked`.

Absence of a mention is deliberately NOT a risk (a change can verify without saying so) — only an explicitly named risk routes. No webhook context → NO output.

## Outputs

- `source_evidence_annotation` (always, on webhook context) — `emission touches webhook handling (<source>)`.
- `advisory_governance_result` (only on a named risk) — "webhook risk named … verify signature + replay protection", metadata `{risks, source}`.
- `routing_hint` (only on a named risk) — `role="security"`, `priority="high"`.

## Boundary (EM-safe)

It flags webhook risk and suggests security review; it never accepts a webhook event, executes a mutation, or sends a notification — it cannot write canonical state, approve/sign off, resolve compliance, or block CI (ADR-0007/0008/0013). Every wire-bound field is re-screened by `run_mod` (FX-SEC-001).

## References

ADR-0008 (evidence adapters, not state authorities), ADR-0013 (mod execution contract). See the [mod safety contract](../README.md) and [references.md](references.md).
