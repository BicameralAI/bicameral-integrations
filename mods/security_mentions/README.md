# Security Mentions Mod

Status: Scoped

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
