# Granola Connector

Provider-facing Granola (meeting transcripts) client and auth documentation.

## Modes

- **Passive** — poll recent meeting transcripts by `ended_at` watermark and
  parse each item into a neutral `Observation` (`parse_transcript`).

The live HTTP poll, watermark two-phase commit, and API-key resolution stay in
the operator runtime (see `auth.md`); this connector is the parse surface only.

## Surface

- `parse_transcript(item)` — Granola transcript → `Observation`
  (`transcript_text` → excerpt with title fallback; first participant → author;
  `ended_at` → timestamp; `id` → ref).
- `GranolaConnector` — connector identity and capabilities (`PASSIVE`).
