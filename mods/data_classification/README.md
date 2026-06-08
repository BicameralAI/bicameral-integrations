# Data Classification Mod

Status: Scoped

Advisory mod for classifying sensitive evidence before it is routed, reviewed,
or proposed for outbound notification.

## Scope

- PII, secrets, credentials, tokens, PHI, payment data, customer records, and
  internal incident details.
- Evidence excerpts that should be minimized, tokenized, redacted, or gated.
- Source types that should be treated as restricted until classified.
- Notification destinations that are too broad for sensitive content.

## Outputs

- `source_evidence_annotation`
- `routing_hint`
- `advisory_governance_result`

## Boundary

This mod may classify and annotate evidence. It must not delete source evidence,
resolve compliance, or send notifications.

## References

See [references.md](references.md).
