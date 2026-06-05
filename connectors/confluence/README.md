# Confluence Connector

Read-only evidence connector: it parses Confluence Cloud page content objects
into neutral `Observation`s. **Status: Beta** (ADR-0012; catalog
documentation/knowledge, priority P1, default trust tier T1/T3). A documentation
adapter from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Active** — REST `GET /wiki/rest/api/content/{id}?expand=body.storage` returns
  a content object whose `body.storage.value` is the XHTML storage body
  (`parse_content`). Read-only evidence; no canonical writes (ADR-0008).
- **Passive** — periodic content polling over a space (same content shape).
- **Webhook** — `page_created` / `page_updated` events (live receipt + signature
  deferred; see [`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its content-object → `runtime.deliver_poll` → reference sink
path is proven end-to-end by `runtime/tests/test_runtime.py`, with **zero
cross-repo dependency**. Live (gateway emission) is now operator-actionable —
`GatewaySink` is real (bot #109 landed, PR #131); an operator configures it
against a real gateway to go Live.

## Surface

- `parse_content(content)` — Confluence REST content object → `Observation`. The
  `body.storage.value` XHTML is flattened to review text (falling back to `title`,
  then a `confluence-page` terminal floor); `id` → ref; `_links.base + _links.webui`
  → ref url; `kind="page"`.
- `_strip_storage_html(value)` — a **lossy, best-effort** XHTML-storage flattener
  (tag removal + entity unescape + whitespace collapse). It is **not** a
  sanitizer: script/style text content survives as plain text. The security gate
  is the emission-time secret/PII screen, not this flattener.
- `ConfluenceConnector` — identity + capabilities (`ACTIVE`, `PASSIVE`, `WEBHOOK`);
  `observations()` parses one content object.

## Verification

Verification is **deferred**. Confluence Cloud has no payload signature scheme
confirmable from current docs — the HMAC `X-Hub-Signature` scheme applies to
Confluence **Data Center**, not Cloud (Cloud webhooks are Connect/app-context).
Per verify-before-cite, no `verify()` is shipped on uncertain ground this cycle;
the connector is proven through the poll path. See [`auth.md`](auth.md).

## References

- Auth model (deferred): [auth.md](auth.md)
