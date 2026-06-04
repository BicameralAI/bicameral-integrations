# Fathom Connector

Provider-facing Fathom (meeting intelligence) client and auth documentation.

## Modes

- **Passive** — poll `GET /meetings` (cursor pagination) and parse each meeting
  item into a neutral `Observation` (`parse_meeting`).
- **Webhook** — the `new-meeting-content-ready` event payload is a meeting
  object of the same shape, so it parses through the same surface.

The live REST poll, API-key resolution, and Svix signature verification are
deferred this cycle (see `auth.md`); this connector is the parse surface only.

## Surface

- `parse_meeting(meeting)` — Fathom meeting → `Observation` (transcript →
  excerpt, with summary/title fallback; `recorded_by.name` → author;
  `recording_end_time`/`created_at` → timestamp; `recording_id` → ref).
- `FathomConnector` — connector identity and capabilities (`PASSIVE`, `WEBHOOK`).
