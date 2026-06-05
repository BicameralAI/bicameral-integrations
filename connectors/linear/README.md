# Linear Connector

Provider-facing Linear (issue tracking) client and auth documentation.

## Modes

- **Webhook** (primary) — the event envelope `{action, type, actor, data,
  updatedFrom, ...}` carries a fully-serialized entity plus change context a
  poll cannot; `parse_event` maps an Issue event to a neutral `Observation`.
- **Active** — GraphQL fetch as a fallback (deferred this cycle).

`Linear-Signature` verification (hex HMAC-SHA256 over the raw body + 60 s
anti-replay window) and best-effort `webhookId` dedup are implemented in
`verify()` / `normalize_event()`. The live HTTP receipt, GraphQL path, and
API-key/secret resolution stay in the operator runtime (see `auth.md`).

## Readiness: Beta (ADR-0012)

First connector promoted to **Beta**: its signed-webhook →
`runtime.deliver_webhook` → reference sink path is proven end-to-end by
`runtime/tests/test_runtime.py`, with **zero cross-repo dependency**. Live (gateway emission) is now operator-actionable — `GatewaySink` is real (bot #109 landed, PR #131); an operator configures it against a real gateway to go Live.

## Surface

- `parse_event(event)` — Linear webhook event → `Observation` (`identifier` +
  `title` → title; `description` → excerpt; `actor.name` → author; `createdAt`
  → timestamp; `action`/`type`/`organizationId` → `metadata`).
- `LinearConnector` — connector identity and capabilities (`WEBHOOK`, `ACTIVE`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
