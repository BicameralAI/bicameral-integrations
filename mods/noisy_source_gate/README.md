# Noisy Source Gate Mod

Status: Built (FX-MOD-003) — `NoisySourceGateMod` in [`connector.py`](connector.py), run via `mods.contract.run_mod`.

Reads `emission.source_id`; for a high-noise source (`slack`/`granola`/`fathom` — chat + meeting
transcripts, explicit config-as-code) emits a `routing_hint` (reviewer, low priority) + an
`advisory_governance_result` suggesting a manual gate unless the source's trust is operator-raised.
A non-noisy source yields nothing. Advisory only (ADR-0008); it suggests, never enforces.

Advisory mod for gating high-noise evidence sources. High-volume, low-signal
channels (Slack chat, Granola/Fathom meeting transcripts) can flood the candidate store; this
mod recommends manual review gating for them unless the operator has explicitly
raised the source's trust. Advisory only: it suggests a gate; it never enforces
one (see the [mod safety contract](../README.md)).

## Scope

- Evidence originating from the high-noise sources currently gated: **`slack`** (chat) and
  **`granola`** / **`fathom`** (meeting transcripts). The set is explicit config-as-code
  (`_NOISY_SOURCES`) and extends as new chat/transcript connectors land.
- Source-trust configuration: respect an operator-raised trust tier; otherwise
  recommend manual gating (the trust exception is operator-side — surfaced in the message).

## Outputs

- `routing_hint`
- `advisory_governance_result`

## References

See [references.md](references.md).
