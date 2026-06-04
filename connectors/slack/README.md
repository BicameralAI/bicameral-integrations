# Slack Connector

Provider-facing Slack adapter. **Status: Beta** (ADR-0012; catalog communication,
priority P0, default trust tier T2/T3). A Phase-1 foundation candidate from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Webhook** — a Slack message, delivered either as a bare message object or
  wrapped in an Events-API `event_callback` envelope, maps to one neutral
  `Observation` (`parse_message`). This is the read/ingest evidence surface;
  notify/write (T3+) is deferred (ADR-0008, evidence before action).

Slack `v0` request-signature verification (`X-Slack-Signature` over
`v0:{ts}:{body}` + a 5-minute `X-Slack-Request-Timestamp` replay window) and
best-effort `event_id` dedup are implemented in `verify()` / `normalize_event()`;
the signed `url_verification` handshake normalizes to `[]`. The live Events-API
receipt and secret resolution stay in the operator runtime (see
[`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its signed-webhook → `runtime.deliver_webhook` → reference
sink path is proven end-to-end by `runtime/tests/test_runtime.py`, with **zero
cross-repo dependency**. Live (gateway emission) remains gated on bicameral-bot
#109.

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
