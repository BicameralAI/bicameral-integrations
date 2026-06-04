# Sentry Connector

Provider-facing Sentry adapter. **Status: Prototype** (catalog
observability/incident-evidence, priority P1, default trust tier T1). From the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Webhook** — a Sentry issue webhook event (wrapping `data.issue`) maps to one
  neutral `Observation` (`parse_issue`). Read-only runtime-error/issue evidence;
  no canonical writes (ADR-0008).

The live Events-API receipt and `Sentry-Hook-Signature` (HMAC-SHA256)
verification are deferred this cycle (see [`auth.md`](auth.md)); this connector
is the parse surface only.

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
