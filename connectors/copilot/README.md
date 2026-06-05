# GitHub Copilot Connector

Read-only evidence connector: it parses GitHub Copilot **aggregate** usage-metrics days
into neutral `Observation`s. **Status: Beta** (ADR-0012; catalog developer-AI tooling,
priority P1, default trust tier T1). A developer-AI-leverage adapter from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Active** — REST `GET /orgs/{org}/copilot/metrics` (also enterprise/team scopes) returns
  a daily array of aggregate metrics objects (`parse_metrics_day`). Read-only evidence; no
  canonical writes (ADR-0008). **Poll-only — GitHub publishes no webhooks for this data.**

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its metrics-object → `runtime.deliver_poll` → reference sink path is
proven end-to-end by `runtime/tests/test_runtime.py`, with **zero cross-repo dependency**.
Live (gateway emission) is now operator-actionable — `GatewaySink` is real (bot #109 landed,
PR #131); an operator configures it against a real gateway to go Live.

## Surface

- `parse_metrics_day(day)` — one Copilot aggregate-metrics day → `Observation`. The excerpt
  is a concise textual summary of the day's aggregate counts (`total_active_users` /
  `total_engaged_users` + the `copilot_ide_code_completions` / `copilot_ide_chat` /
  `copilot_dotcom_chat` / `copilot_dotcom_pull_requests` engaged counts); `date` → ref
  (`copilot:metrics:<date>`); `kind="usage_metrics"`.
- `CopilotConnector` — identity + capabilities (`ACTIVE`); `observations()` parses one day.

## Privacy

This connector ingests **only the aggregate metrics object**, which contains **no
per-developer identity** by design ([GitHub Docs](https://docs.github.com/en/rest/copilot/copilot-metrics)).
The newer per-user NDJSON "usage metrics" report API (signed download URLs, per-user rows) is
**deferred** — it carries PII and belongs behind a future redaction-and-pass model.

## References

- Auth model (deferred): [auth.md](auth.md)
