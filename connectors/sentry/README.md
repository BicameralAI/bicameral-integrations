# Sentry Connector

Provider-facing Sentry adapter. **Status: Beta** (ADR-0012; catalog
observability/incident-evidence, priority P1, default trust tier T1). From the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Webhook** — a Sentry issue webhook event (wrapping `data.issue`) maps to one
  neutral `Observation` (`parse_issue`). Read-only runtime-error/issue evidence;
  no canonical writes (ADR-0008).

`Sentry-Hook-Signature` (hex HMAC-SHA256 over the raw body) verification and
best-effort dedup are implemented in `verify()` / `normalize_event()`. The live
Events-API receipt and secret resolution stay in the operator runtime (see
[`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its signed-webhook → `runtime.deliver_webhook` → reference
sink path is proven end-to-end by `runtime/tests/test_runtime.py`, with **zero
cross-repo dependency**. Live (gateway emission) is now operator-actionable — `GatewaySink` is real (bot #109 landed, PR #131); an operator configures it against a real gateway to go Live.

## Surface

- `parse_issue(event)` — Sentry issue event → `Observation`. Unwraps the
  `data.issue` envelope (falls back to a bare issue object); `title` → excerpt,
  with `culprit` then `shortId` then `id` as terminal fallback; `id` → ref;
  `permalink` → ref url; `firstSeen` → timestamp; `action`/`level`/`status`/
  `shortId` → metadata.
- `SentryConnector` — connector identity and capabilities (`WEBHOOK`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
