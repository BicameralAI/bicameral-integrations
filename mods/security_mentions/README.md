# Security Mentions Mod

Status: Built (FX-MOD-004) — `SecurityMentionsMod` in [`connector.py`](connector.py), run via `mods.contract.run_mod`.

Scans `title`+`body`+evidence excerpts for **whole-word** security keywords (auth/token/secret/
credential/oauth/webhook/cve/…), case-insensitive + deterministic (sorted). On a match: emits an
`advisory_governance_result`, a security `routing_hint`, and a `source_evidence_annotation`. Surfaces
*mentions* (the word "token"), never secrets — **complements, never replaces** FX-SEC-001 (the producer
screen + `run_mod`'s input re-screen already removed any real secret; `run_mod` re-screens this output).

Advisory mod for surfacing security-relevant mentions in adapter evidence —
authentication, tokens, secrets, PII, webhook verification, and transport
exposure — so a reviewer sees the security surface of a change at a glance.
Complements (does not replace) the producer-side sensitive-data hard-screen
(`FX-SEC-001`); this mod *annotates and routes*, it never blocks or approves
(see the [mod safety contract](../README.md)).

## Scope

- Auth / token / credential and secret mentions in evidence text.
- PII and sensitive-data references that warrant handling review.
- Webhook-verification posture and transport-exposure signals.

## Outputs

- `source_evidence_annotation`
- `routing_hint`
- `advisory_governance_result`

## References

See [references.md](references.md).
