# Noisy Source Gate Mod

Status: Scoped

Advisory mod for gating high-noise evidence sources. High-volume, low-signal
channels (Slack, email, meeting transcripts) can flood the candidate store; this
mod recommends manual review gating for them unless the operator has explicitly
raised the source's trust. Advisory only: it suggests a gate; it never enforces
one (see the [mod safety contract](../README.md)).

## Scope

- Evidence originating from high-noise sources (Slack, email, meetings, chat).
- Source-trust configuration: respect an operator-raised trust tier; otherwise
  recommend manual gating.
- Volume / signal-density heuristics that distinguish actionable evidence from
  routine chatter.

## Outputs

- `routing_hint`
- `advisory_governance_result`

## References

See [references.md](references.md).
