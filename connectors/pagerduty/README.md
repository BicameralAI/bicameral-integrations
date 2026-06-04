# PagerDuty Connector

Provider-facing PagerDuty adapter. **Status: Prototype** (catalog
observability/incident-evidence, priority P1, default trust tier T1). From the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Webhook** — a PagerDuty v3 webhook envelope (`event.data` for an incident)
  maps to one neutral `Observation` (`parse_event`). Read-only incident/on-call
  evidence; no canonical writes (ADR-0008).

The live webhook receipt and `X-PagerDuty-Signature` verification are deferred
this cycle (see [`auth.md`](auth.md)); this connector is the parse surface only.

## Surface

- `parse_event(envelope)` — PagerDuty v3 incident event → `Observation`. Unwraps
  the nested `event.data` envelope (both levels guarded); `title` → excerpt,
  with `summary` then `id` as terminal fallback; `id` → ref; `html_url` → ref
  url; `created_at` (fallback `event.occurred_at`) → timestamp;
  `event_type`/`status`/`urgency` → metadata.
- `PagerDutyConnector` — connector identity and capabilities (`WEBHOOK`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
