# Slack Connector

Provider-facing Slack adapter. **Status: Prototype** (catalog communication,
priority P0, default trust tier T2/T3). A Phase-1 foundation candidate from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Webhook** — a Slack message, delivered either as a bare message object or
  wrapped in an Events-API `event_callback` envelope, maps to one neutral
  `Observation` (`parse_message`). This is the read/ingest evidence surface;
  notify/write (T3+) is deferred (ADR-0008, evidence before action).

The live Events-API receipt and webhook signature verification are deferred
this cycle (see [`auth.md`](auth.md)); this connector is the parse surface only.

## Surface

- `parse_message(payload)` — Slack message → `Observation`. Unwraps the
  `event_callback` envelope and edit subtypes (`message_changed`, whose content
  lives in a nested `message` object); `text` → excerpt, with a non-empty
  `(no text) channel:ts` locating fallback so the emission contract always
  holds; `user` → author; `channel:ts` → ref; `channel`/`type` → `metadata`.
- `SlackConnector` — connector identity and capabilities (`WEBHOOK`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
