# PagerDuty Connector

Provider-facing PagerDuty adapter. **Status: Beta** (ADR-0012; catalog
observability/incident-evidence, priority P1, default trust tier T1). From the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Webhook** — a PagerDuty v3 webhook envelope (`event.data` for an incident)
  maps to one neutral `Observation` (`parse_event`). Read-only incident/on-call
  evidence; no canonical writes (ADR-0008).

`X-PagerDuty-Signature` verification (multi-signature `v1=<hex>,v1=<hex>`
rotation **membership** — accept if any matches) and best-effort dedup are
implemented in `verify()` / `normalize_event()`. The live webhook receipt and
secret resolution stay in the operator runtime (see [`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its signed-webhook → `runtime.deliver_webhook` → reference
sink path is proven end-to-end by `runtime/tests/test_runtime.py` (the test
places the valid signature second in the rotation set to prove membership), with
**zero cross-repo dependency**. Live (gateway emission) is now operator-actionable — `GatewaySink` is real (bot #109 landed, PR #131); an operator configures it against a real gateway to go Live.

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
