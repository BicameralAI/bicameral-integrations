# Webhook Risk Mod

Status: Scoped

Advisory mod for webhook safety signals across signature verification, replay
protection, event schema handling, idempotency, and outbound side effects.

## Scope

- Missing or weak signature verification.
- Missing timestamp tolerance, replay protection, or deduplication.
- Unknown event schemas that should route to quarantine.
- Webhook-triggered writes without policy.
- Provider event spoofing, broad notification, or sensitive-content leakage.

## Outputs

- `advisory_governance_result`
- `routing_hint`
- `source_evidence_annotation`

## Boundary

This mod may flag webhook risk and suggest review routing. It must not accept
webhook events, execute mutations, or send notifications.

## References

See [references.md](references.md).
