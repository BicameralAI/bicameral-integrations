# Google Drive Connector

The Google Drive connector maps Google Docs/Drive document payloads into provider-neutral `Observation` objects.

## Table of Contents

- [Status](#status)
- [Modes](#modes)
- [Public Surface](#public-surface)
- [Input and Output](#input-and-output)
- [Auth and Runtime Boundary](#auth-and-runtime-boundary)
- [Development](#development)
- [Related Documentation](#related-documentation)

## Status

Implemented:

- Google Docs and Drive document URL parsing.
- Google Docs `documents.get` structured body flattening.
- Paragraph and table traversal.
- Heading decoration for reviewable text anchors.
- End-to-end normalization coverage through adapter core.

Deferred:

- Live Docs API calls.
- OAuth credential resolution and refresh.
- Folder polling.
- Push-notification channel handling.

## Modes

| Mode | Status | Notes |
| --- | --- | --- |
| Active | Declared, parse surface implemented | Runtime `documents.get` fetch remains deferred. |
| Passive | Declared, live polling deferred | Folder polling belongs to the operator runtime. |
| Webhook | Declared, live push channel handling deferred | Channel lifecycle and receipt handling are not implemented here. |

## Public Surface

| Symbol | Purpose |
| --- | --- |
| [`parse_gdrive_url(url)`](connector.py) | Extracts a document ID from supported Google Docs/Drive URLs. |
| [`extract_document_text(document)`](connector.py) | Flattens paragraphs and tables from a Docs API response. |
| [`parse_document(document)`](connector.py) | Maps a Docs API response to an `Observation`. |
| [`GoogleDriveConnector`](connector.py) | Declares `source_id = "google_drive"` and active/passive/webhook capabilities. |
| `GoogleDriveConnector.can_handle_ref(ref)` | Accepts Google Drive source refs and supported Docs/Drive URLs. |
| `GoogleDriveConnector.observations(payload)` | Returns one parsed observation for a document payload. |

## Input and Output

Expected input is shaped like [`fixtures/doc_decision.json`](fixtures/doc_decision.json), matching a Google Docs `documents.get` response.

The connector preserves:

- `documentId` as the source ref.
- Document title.
- Flattened document text as the excerpt, falling back to title.
- Heading style decoration in the flattened text.

`parse_gdrive_url` validates URL shape only; it does not prove the document exists or that credentials can access it.

## Auth and Runtime Boundary

Credential keys and runtime expectations are documented in [`auth.md`](auth.md). OAuth, live API calls, refresh handling, folder polling, and push-channel lifecycle stay in the operator runtime.

The connector must not persist credentials, call the gateway directly, write decisions, or bypass adapter validation.

## Development

```bash
pytest connectors/google_drive/tests -q
```

## Related Documentation

- [Connectors](../README.md)
- [Adapter Core](../../adapter/core/README.md)
- [Feature Index](../../docs/FEATURE_INDEX.md)
