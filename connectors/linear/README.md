# Linear Connector

Provider-facing Linear (issue tracking) client and auth documentation.

## Modes

- **Webhook** (primary) — the event envelope `{action, type, actor, data,
  updatedFrom, ...}` carries a fully-serialized entity plus change context a
  poll cannot; `parse_event` maps an Issue event to a neutral `Observation`.
- **Active** — GraphQL fetch as a fallback (deferred this cycle).

The live GraphQL path, API-key resolution, and `Linear-Signature` verification
(+ 60 s anti-replay) are deferred this cycle (see `auth.md`); this connector is
the parse surface only.

## Surface

- `parse_event(event)` — Linear webhook event → `Observation` (`identifier` +
  `title` → title; `description` → excerpt; `actor.name` → author; `createdAt`
  → timestamp; `action`/`type`/`organizationId` → `metadata`).
- `LinearConnector` — connector identity and capabilities (`WEBHOOK`, `ACTIVE`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
