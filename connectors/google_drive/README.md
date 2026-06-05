# Google Drive Connector

Read-only Google Drive / Google Docs evidence adapter: parses a Docs response
into a neutral `Observation`. **Status: Beta** (ADR-0012).

## Modes

- **Active** — parse a Google Docs `documents.get` response into a neutral
  `Observation` (`parse_document`). URL routing via `parse_gdrive_url` /
  `can_handle_ref`.
- **Passive / Webhook** — folder polling and push-notification channels are
  declared in capabilities; their live paths remain **deferred** to the operator
  runtime.

## Surface

- `parse_gdrive_url(url)` — extract a document id from a Docs/Drive URL.
- `extract_document_text(document)` — flatten the structured document body
  (paragraphs, tables, heading decoration) to plain text.
- `parse_document(document)` — build the provider-neutral `Observation`.
- `GoogleDriveConnector` — connector identity and capabilities.

The live Docs API call and OAuth credential resolution remain **deferred** to
the operator runtime (see [`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its `runtime.deliver_poll` → reference sink path is proven
end-to-end by `runtime/tests/test_runtime.py`, with **zero cross-repo
dependency**. Live (gateway emission) remains gated on bicameral-bot #109.

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
