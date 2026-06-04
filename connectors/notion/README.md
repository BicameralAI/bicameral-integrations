# Notion Connector

Provider-facing Notion adapter. **Status: Prototype** (catalog docs, priority
P0, default trust tier T1/T3). A Phase-1 foundation candidate from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Active** — a Notion page object maps to one neutral `Observation`
  (`parse_page`). No canonical-state writes — this is an evidence adapter, not a
  state authority (ADR-0008).
- **Webhook** — page-change events carry a page object of the same shape and
  parse through the same surface.

The live Notion API fetch, block-content retrieval, and OAuth credential
resolution are deferred this cycle (see [`auth.md`](auth.md)); this connector is
the parse surface only.

## Surface

- `parse_page(page)` — Notion page → `Observation` (title read from the property
  whose `type == "title"`, joining its `plain_text` runs, with `id` then a
  `notion-page` literal as terminal fallback; title → excerpt; `url` → ref url;
  `created_by.id` → author; `last_edited_time`/`created_time` → timestamp).
- `NotionConnector` — connector identity and capabilities (`ACTIVE`, `WEBHOOK`).

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
