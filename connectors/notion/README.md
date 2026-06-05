# Notion Connector

Provider-facing Notion adapter. **Status: Beta** (ADR-0012; catalog docs,
priority P0, default trust tier T1/T3). A Phase-1 foundation candidate from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Active** — a Notion page object maps to one neutral `Observation`
  (`parse_page`). No canonical-state writes — this is an evidence adapter, not a
  state authority (ADR-0008).
- **Webhook** — page-change events carry a page object of the same shape and
  parse through the same surface.

`X-Notion-Signature` (hex HMAC-SHA256 over the raw body with the subscription
verification token, `sha256=`-prefixed — the prefix is required) verification and
best-effort dedup are implemented in `verify()` / `normalize_event()`. The live
Notion API fetch, block-content retrieval, OAuth, and HTTP receipt stay in the
operator runtime (see [`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its signed-webhook → `runtime.deliver_webhook` → reference
sink path is proven end-to-end by `runtime/tests/test_runtime.py`, with **zero
cross-repo dependency**. Live (gateway emission) is now operator-actionable — `GatewaySink` is real (bot #109 landed, PR #131); an operator configures it against a real gateway to go Live.

## Surface

- `parse_page(page)` — Notion page → `Observation` (title read from the property
  whose `type == "title"`, joining its `plain_text` runs, with `id` then a
  `notion-page` literal as terminal fallback; title → excerpt; `url` → ref url;
  `created_by.id` → author; `last_edited_time`/`created_time` → timestamp).
- `NotionConnector` — connector identity and capabilities (`ACTIVE`, `WEBHOOK`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
