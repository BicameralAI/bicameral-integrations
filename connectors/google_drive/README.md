# Google Drive Connector

Provider-facing Google Drive and Google Docs client and auth documentation.

## Modes

- **Active** — parse a Google Docs `documents.get` response into a neutral
  `Observation` (`parse_document`). URL routing via `parse_gdrive_url` /
  `can_handle_ref`.
- **Passive / Webhook** — folder polling and push-notification channels are
  declared in capabilities but their live paths are deferred this cycle.

## Surface

- `parse_gdrive_url(url)` — extract a document id from a Docs/Drive URL.
- `extract_document_text(document)` — flatten the structured document body
  (paragraphs, tables, heading decoration) to plain text.
- `parse_document(document)` — build the provider-neutral `Observation`.
- `GoogleDriveConnector` — connector identity and capabilities.

The live Docs API call and OAuth credential resolution stay in the operator
runtime (see [`auth.md`](auth.md)); this connector is the parse surface only.

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
