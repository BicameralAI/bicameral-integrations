# OpenAI Admin Connector

Read-only evidence connector: it parses OpenAI organization **audit-log** events into neutral
`Observation`s — governance/security evidence with actor identity dropped. **Status: Beta**
(ADR-0012; catalog developer-AI / governance, priority P1, default trust tier T1).

## Modes

- **Active** — Admin API `GET /v1/organization/audit_logs` returns org audit events
  (`parse_audit_log`). Read-only evidence; no canonical writes (ADR-0008). **Poll-only — OpenAI
  publishes no webhooks for audit logs.**

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its event → `runtime.deliver_poll` → reference sink path is proven
end-to-end by `runtime/tests/test_runtime.py`, with **zero cross-repo dependency**, and the
actor-identity drop is proven end-to-end. Live (gateway emission) is now operator-actionable.

## Surface

- `parse_audit_log(event)` — an OpenAI audit event → `Observation`. Excerpt = event `type` +
  project name + the non-PII `actor.type` (`session`/`api_key`) + UTC timestamp; `id` → ref
  (`openai-audit-event` floor); `kind="audit_event"`. The excerpt is passed through `redact()`
  defensively.
- `OpenAIAdminConnector` — identity + capabilities (`ACTIVE`); `observations()` parses one event.

## Privacy

OpenAI audit events carry **actor identity** (`actor.session.user.email`,
`actor.api_key.user.email`, `actor.session.ip_address`, user ids). **FX-SEC-001 screens
secret/PHI/PAN but NOT a generic email or IP**, and `redact()` does not scrub IPv4 — so the
**sole control is parse-time exclusion**: `parse_audit_log` **never reads** the actor email /
id / ip_address. Only the non-PII `actor.type` enum (`session`/`api_key`, allowlisted) is
surfaced. Per-actor filtering / attribution is deferred behind the PII redaction-and-pass model.

## References

- Auth model (deferred): [auth.md](auth.md)
