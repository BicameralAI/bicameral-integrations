# Zendesk Connector

Provider-facing Zendesk adapter. **Status: Beta** (ADR-0012; catalog
support/customer-success, priority P1, default trust tier T1/T5). From the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Webhook** — a Zendesk event-subscription delivery (`{type, account_id,
  subject, time, detail, event}`) for a ticket maps to one neutral
  `Observation` (`parse_ticket`). Read-only support/customer evidence; no
  canonical writes (ADR-0008). Triage/reply (T3+) is out of scope (that would be
  `bicameral-mcp`).
- **Active** — REST poll (`/api/v2`) as a fallback (deferred this cycle).

`X-Zendesk-Webhook-Signature` (Base64 HMAC-SHA256 over `timestamp + body`) +
`X-Zendesk-Webhook-Signature-Timestamp` verification and best-effort dedup are
implemented in `verify()` / `normalize_event()`. The live REST receipt, OAuth,
secret resolution, and a **redaction-and-pass model for live ticket-body
ingest** stay in the operator runtime (see [`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its signed-webhook → `runtime.deliver_webhook` → reference
sink path is proven end-to-end by `runtime/tests/test_runtime.py`, with **zero
cross-repo dependency**. Live (gateway emission) is now operator-actionable — `GatewaySink` is real (bot #109 landed, PR #131); an operator configures it against a real gateway to go Live.

## Surface

- `parse_ticket(event)` — Zendesk ticket event → `Observation`. Excerpt is the
  ticket **subject** (a plain string), never a description/comment body
  (customer-PII-dense); `detail.id` → ref (falls back to parsing `zen:ticket:<id>`
  from `subject`, then a `zendesk-ticket` floor); `detail.url` → ref url;
  `requester_id` → author; `updated_at`/`time` → timestamp;
  `type`/`status`/`priority`/`via.channel` → metadata. Type-defensive (SG-I).
- `ZendeskConnector` — connector identity, capabilities (`WEBHOOK`, `ACTIVE`),
  `verify()`/`normalize_event()`.

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
