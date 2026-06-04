# Fathom Connector

Provider-facing Fathom (meeting intelligence) client and auth documentation.

## Modes

- **Passive** — poll `GET /meetings` (cursor pagination) and parse each meeting
  item into a neutral `Observation` (`parse_meeting`).
- **Webhook** — the `new-meeting-content-ready` event payload is a meeting
  object of the same shape, so it parses through the same surface.

Svix / Standard-Webhooks signature verification (+ freshness window) and
best-effort `webhook-id` dedup are implemented in `verify()` / `normalize_event()`.
The live REST poll, API-key resolution, and HTTP receipt stay in the operator
runtime (see `auth.md`).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its signed-webhook → `runtime.deliver_webhook` → reference
sink path is proven end-to-end by `runtime/tests/test_runtime.py`, with **zero
cross-repo dependency**. Live (gateway emission) remains gated on bicameral-bot
#109.

## Surface

- `parse_meeting(meeting)` — Fathom meeting → `Observation` (transcript →
  excerpt, with summary/title fallback; `recorded_by.name` → author;
  `recording_end_time`/`created_at` → timestamp; `recording_id` → ref).
- `FathomConnector` — connector identity and capabilities (`PASSIVE`, `WEBHOOK`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
