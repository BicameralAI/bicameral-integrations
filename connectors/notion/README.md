# Notion Connector

Provider-facing Notion adapter. **Status: Beta** (ADR-0012; catalog docs,
priority P0, default trust tier T1/T3). A Phase-1 foundation candidate from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Webhook** (live mode) — a page-change delivery is a thin EVENT envelope
  (`{id, type, entity:{id,type}, timestamp}`) that carries **no** page content.
  `parse_event` maps it to a page-changed **pointer** `Observation` keyed by the
  page `entity.id` (the stable subject — never the ephemeral event id), with
  title `Notion <event_type>`. No canonical-state writes — evidence adapter, not
  a state authority (ADR-0008).
- **Active** (deferred) — the deferred `pages.retrieve` fetch returns a full
  Notion page object, which maps through `parse_page` (title from the
  `type == "title"` property). The webhook pointer's `entity.id` is the fetch key.

`X-Notion-Signature` (hex HMAC-SHA256 over the raw body with the subscription
verification token, `sha256=`-prefixed — the prefix is required) verification and
dedup (by event id, with a body-hash fallback so a signed id-less body cannot
bypass it) are implemented in `verify()` / `normalize_event()`. The live Notion
API fetch, block-content retrieval, OAuth, and HTTP receipt stay in the operator
runtime (see [`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its signed-webhook → `runtime.deliver_webhook` → reference
sink path is proven end-to-end by `runtime/tests/test_runtime.py`, with **zero
cross-repo dependency**. Live (gateway emission) is now operator-actionable — `GatewaySink` is real (bot #109 landed, PR #131); an operator configures it against a real gateway to go Live.

## Surface

- `parse_event(envelope)` — Notion webhook delivery envelope → page-changed
  pointer `Observation` (`entity.id` → ref subject; `Notion <type>` → title;
  `timestamp` → timestamp; no page content). This is the live webhook surface.
- `parse_page(page)` — full Notion page object (deferred active fetch) →
  `Observation` (title read from the property whose `type == "title"`, with a
  `str`-coerced `id` then a `notion-page` literal as terminal fallback; title →
  excerpt; `url` → ref url; `created_by.id` → author; timestamp).
- `NotionConnector` — connector identity and capabilities (`ACTIVE`, `WEBHOOK`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
