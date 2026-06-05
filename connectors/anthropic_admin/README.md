# Anthropic Admin Connector

Read-only evidence connector: it parses Anthropic organization **usage** buckets into neutral
`Observation`s — aggregate AI-leverage/cost evidence, PII-free. **Status: Beta** (ADR-0012;
catalog developer-AI / governance, priority P1, default trust tier T1).

## Modes

- **Active** — Usage & Cost Admin API `GET /v1/organizations/usage_report/messages` returns
  time-bucketed usage records (`parse_usage`). Read-only evidence; no canonical writes
  (ADR-0008). **Poll-only — no webhooks** (poll ≤ once/min).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its bucket → `runtime.deliver_poll` → reference sink path is proven
end-to-end by `runtime/tests/test_runtime.py`, with **zero cross-repo dependency**. Live
(gateway emission) is now operator-actionable.

## Surface

- `parse_usage(bucket)` — an Anthropic usage time-bucket → `Observation`. Excerpt = summed
  input/output token totals + distinct models across the bucket's `results`; `starting_at` →
  ref (`anthropic-usage` floor); `kind="usage_metrics"`. Input = `uncached_input_tokens` +
  `cache_read_input_tokens` + `cache_creation_input_tokens`.
- `AnthropicAdminConnector` — identity + capabilities (`ACTIVE`); `observations()` parses one bucket.

## Privacy

The Usage & Cost API is **aggregate and PII-free** by design — grouping dimensions are opaque
ids (`workspace_id`, `api_key_id`), model names, and service tiers; there is no user email or
name. The connector surfaces only the aggregate token totals + models (the opaque
`workspace_id`/`api_key_id` are not even included in the excerpt). Per-user cost/attribution is a
**separate** API (Claude Code Analytics — per-user PII) and is **deferred** behind the PII
redaction-and-pass model. The `/cost_report` rich parse is deferred (usage tokens first).

## References

- Auth model (deferred): [auth.md](auth.md)
