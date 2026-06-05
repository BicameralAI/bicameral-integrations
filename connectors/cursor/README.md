# Cursor Connector

Read-only evidence connector: it parses Cursor team **daily-usage** rows into neutral,
**PII-free** `Observation`s. **Status: Beta** (ADR-0012; catalog developer-AI tooling,
priority P1, default trust tier T1). A developer-AI-leverage adapter from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Active** — Admin API `POST /teams/daily-usage-data` returns per-user-day usage rows
  (`parse_usage_day`). Read-only evidence; no canonical writes (ADR-0008). **Poll-only —
  Cursor publishes no webhooks** (docs recommend polling at most hourly).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its usage-row → `runtime.deliver_poll` → reference sink path is proven
end-to-end by `runtime/tests/test_runtime.py`, with **zero cross-repo dependency**, and the
PII-drop is proven end-to-end (no `@example.com` in the emitted evidence). Live (gateway
emission) is now operator-actionable — `GatewaySink` is real (bot #109 landed, PR #131); an
operator configures it against a real gateway to go Live.

## Surface

- `parse_usage_day(row)` — one Cursor daily-usage row → `Observation`. The excerpt is a concise
  textual summary of the **aggregate** metrics only (`acceptedLinesAdded`, `totalAccepts` /
  `totalApplies`, `agentRequests` / `chatRequests` / `composerRequests`, `mostUsedModel`);
  `day` → ref (`cursor:usage:<day>`, `cursor-usage` floor); `kind="usage_metrics"`.
- `CursorConnector` — identity + capabilities (`ACTIVE`); `observations()` parses one row.

## Privacy (the core design constraint)

Every Cursor daily-usage row carries `email` (PII), and `name` appears in the members/spend
endpoints. **FX-SEC-001 screens secret / PHI / PAN only — it does NOT detect a generic email**,
and it never scans `Observation.metadata`, so there is **no downstream backstop**
([SG-2026-06-05-A](../../docs/SHADOW_GENOME.md)). The **sole** PII control is therefore at parse
time: `parse_usage_day` reads a strict allowlist of non-PII aggregate fields and **never reads
`email` / `name` / `userId` / `clientVersion`**. Per-developer-attributed ingest is deferred
behind a future PII redaction-and-pass model (the same gate as live Zendesk ticket bodies).

## References

- Auth model (deferred): [auth.md](auth.md)
