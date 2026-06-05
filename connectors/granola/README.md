# Granola Connector

Read-only Granola (meeting transcripts) evidence adapter: parses a transcript
payload into a neutral `Observation`. **Status: Beta** (ADR-0012).

## Modes

- **Passive** — poll recent meeting transcripts by `ended_at` watermark and
  parse each item into a neutral `Observation` (`parse_transcript`).

The live HTTP poll, watermark two-phase commit, and API-key resolution remain
**deferred** to the operator runtime (see [`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its `runtime.deliver_poll` → reference sink path is proven
end-to-end by `runtime/tests/test_runtime.py`, with **zero cross-repo
dependency**. Live (gateway emission) is now operator-actionable — `GatewaySink` is real (bot #109 landed, PR #131); an operator configures it against a real gateway to go Live.

## Surface

- `parse_transcript(item)` — Granola transcript → `Observation`
  (`transcript_text` → excerpt with title fallback; first participant → author;
  `ended_at` → timestamp; `id` → ref).
- `GranolaConnector` — connector identity and capabilities (`PASSIVE`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
