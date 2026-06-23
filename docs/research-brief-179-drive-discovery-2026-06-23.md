# Research Brief — Google Drive resource discovery (#179)

**Date**: 2026-06-23
**Analyst**: The Qor-logic Analyst
**Target**: Google Drive discovery/fetch slice for the merged `DiscoveryConnector` surface (#178), mocked/recorded
**Scope**: Drive API surface (`drives.list`/`files.list`), OAuth scopes, the refined shared-drive/`.bicameral` product scope, in-repo reuse map, golden-fixture conformance, error taxonomy, and the transport/auth seam — grounding the #179 plan. **No connector code written this phase.**

---

## Executive Summary

The Drive discovery slice is **largely a recombination of code that already exists in the repo** plus one net-new external surface. The OAuth token path (`RefreshTokenSecretResolver` → access token via `SecretResolver`), the `BearerAuth`/`HttpTransport`/host-pin transport seam, and the document parse surface (`parse_document`/`extract_document_text`) are all built and verified. The **new** surface is resource *listing* — `drives.list` (shared drives) and `files.list` (`.bicameral` project folders + document leaves) — which the repo explicitly deferred (poll_specs.py:331 "Folder-polling (`files.list`) … deferred"). Both new endpoints are verified against Google's v3 reference below. The #180 GitHub connector pattern (injected transport + injected token provider + `RecordedTransport` + `screening.py`) **transfers directly**, with the token provider being the existing `SecretResolver` rather than a new type. No drift found against ADR-0017; one open question (live blocker factory#93) and one integration-sequencing item (`screening.py` lives on the unmerged #180 branch).

## Findings

### F1 — `drives.list`: shared-drive discovery (NEW surface) — VERIFIED

`GET https://www.googleapis.com/drive/v3/drives` (Google Drive API v3 reference, fetched 2026-06-23).
- Params: `pageSize` (int), `pageToken` (str), `q` (str, shared-drive search), `useDomainAdminAccess` (bool — **not** for alpha; we list drives the connected user can see).
- Response: `{ "drives": [Drive], "nextPageToken": str?, "kind": "drive#driveList" }`. Drive fields include `id`, `name`.
- Scopes: `drive` or `drive.readonly`.
- Maps to golden fixture `google-drive-shared-drive.json` (`resource_type: "shared_drive"`, `resource_id: "drive_<id>"`, `uri: https://drive.google.com/drive/folders/<id>`).

### F2 — `files.list`: `.bicameral` project folders + document leaves (NEW surface) — VERIFIED

`GET https://www.googleapis.com/drive/v3/files` (v3 reference, fetched 2026-06-23).
- Params: `q` (filter), `corpora` (default `user`; **use `drive`** for a shared drive), `driveId` (the shared-drive id), `includeItemsFromAllDrives=true`, `supportsAllDrives=true`, `pageSize` (default 100, **max 100** — values above are clamped), `pageToken`, `orderBy`, `fields`, `spaces`.
- Response: `{ "files": [File], "nextPageToken": str?, "kind": "drive#fileList", "incompleteSearch": bool }`. File fields: `id`, `name`, `mimeType`, `parents`, `modifiedTime`, `version`, `webViewLink`, `driveId`.
- **Shared-drive listing requires** `corpora=drive` + `driveId=<id>` + `includeItemsFromAllDrives=true` + `supportsAllDrives=true` together (standard Drive shared-drive contract).
- `.bicameral` discovery query: `q = "name = '.bicameral' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"` within the drive; then list that folder's children (`q = "'<bicameral_folder_id>' in parents and mimeType = 'application/vnd.google-apps.folder'"`) → the **project folders**. Folder mime = `application/vnd.google-apps.folder`; Google Doc mime = `application/vnd.google-apps.document` (consistent with fixture `provider_metadata.mime_type`).
- Maps to golden fixtures `google-drive-folder.json` (`resource_type: "folder"`, parent = shared drive) and `google-drive-document.json` (`resource_type: "document"`, parent = folder, `provider_metadata.mime_type`/`version`).

### F3 — OAuth scopes — confirms ADR-0017 Finding 4 (no drift)

- `documents.get` requires `documents.readonly` / `drive.readonly` / `drive.file` — **NOT `drive.metadata.readonly`** (repo `runtime/poll_specs.py:334`, "verified developers.google.com/docs/api 2026-06-08"; re-confirmed against the action-needed fixture).
- The action-needed golden fixture (`google-drive-action-needed.json`) encodes exactly this: `current_scope: drive.metadata.readonly` → `required_scope: drive.readonly`, `action_needed_reason: "missing_scope"`. This is the **canonical model for the F6 taxonomy**.
- **Minimal alpha scope set**: `drive.readonly` (covers `drives.list` + `files.list` listing **and** document content read) + `documents.readonly` (already declared in `connectors/google_drive/config.json`). The repo's config already declares both — **no config-scope change needed**.

### F4 — Refined product scope (issue #179, 2026-06-18 comment) → resource hierarchy

Discover **shared drives + `.bicameral/<project>/` project folders**, NOT arbitrary folder picking:
- `shared_drive` (via `drives.list`) — `account_label` is the connected Workspace user; **auto-select if exactly one** eligible shared drive, **prompt if multiple** (that selection is bot/UI-side; the connector only *emits* the descriptors).
- `folder` (via `files.list` under `<drive>/.bicameral/`) — the **project folders** are the pickable units; the connector emits them as `folder` descriptors parented to the shared drive.
- `document` (via `files.list` leaf / `documents.get` for content) — leaves inside a project folder.
- **Consumer accounts unsupported**: personal `My Drive` / Gmail are out of scope for team projects → maps to an `action_needed` / `unsupported` outcome (F6), not empty success.
- The convention `<shared drive root>/.bicameral/<project-name>/` means the connector's `list_resources` is **scoped discovery** (shared drives → `.bicameral` children), not a generic folder browser. Project *creation* (`.bicameral/<project>` folder creation when absent) is a **write** → `ProposedAction`/egress (ADR-0017 §4), **out of #179 scope** (discovery is read-only; `create_provider_resource` absent).

### F5 — In-repo reuse map (most of the slice already exists)

| Need | Existing asset | File:line |
|---|---|---|
| OAuth access token (operator-side) | `RefreshTokenSecretResolver` (mints token from refresh token; stdlib form-POST; token-safe) | `runtime/google_oauth.py:43` |
| Secret-by-source_id boundary | `SecretResolver` Protocol + `MappingSecretResolver` | `runtime/secrets.py:15,27` |
| Bearer auth header | `BearerAuth` | `runtime/poll_auth.py` (used at `poll_specs.py:350`) |
| HTTP seam + recorded-transport precedent | `HttpTransport`/`UrllibTransport`/`HttpResponse` | `runtime/poll_client.py` |
| Host-pin SSRF guard | `_pin_host` (deep-audit SG-2026-06-12-B) | `runtime/poll_specs.py:82` |
| Document content parse | `parse_document` / `extract_document_text` (structured-body walk, type-guarded, ≤3 nesting) | `connectors/google_drive/connector.py:131,110` |
| Single-doc GET → Observation precedent | `DocFetchSpec` / `fetch_document` | `runtime/doc_fetch.py:34,58` |
| URL fallback (zero-`files.list` path) | `parse_gdrive_url` | `connectors/google_drive/connector.py:29` |
| Descriptor/item screen (fail-closed) | `screening.py` (`screen_descriptor`/`screen_item`) — **on the #180 branch** | `protocol/provider_acquisition/screening.py` (feat/180) |

### F6 — Error/permission taxonomy → merged `DiscoveryErrorKind` (5 values: `permission_denied`/`action_needed`/`not_found`/`unsupported`/`provider_error`)

| Drive condition | DiscoveryErrorKind | permission_state | note |
|---|---|---|---|
| Insufficient scope (e.g. only `drive.metadata.readonly`) | `ACTION_NEEDED` | `action_needed` | the canonical fixture case; carries `required_scope` |
| Expired / revoked grant (401) | `ACTION_NEEDED` | `action_needed` | re-authorize |
| Shared-drive access denied (403 `insufficientFilePermissions`) | `PERMISSION_DENIED` | `denied` | — |
| Consumer / My-Drive account (no eligible shared drive) | `ACTION_NEEDED` | `action_needed` | "use a Workspace account on an allowed domain" |
| Not found / deleted / trashed (404) | `NOT_FOUND` | — | — |
| Unsupported resource kind (e.g. a Sheet where a Doc is expected) | `UNSUPPORTED` | — | mime not `…google-apps.document`/`folder` |
| Stale/invalid `pageToken` (400) | `PROVIDER_ERROR` | — | restart listing |
| Drive unavailable / 5xx / rate-limit (403 `userRateLimitExceeded` / 429) | `PROVIDER_ERROR` | — | retry |

### F7 — Transport/auth seam: the #180 pattern transfers directly

- The #180 `GitHubDiscoveryConnector` takes an **injected transport** (`GitHubTransport` + `RecordedTransport`) and an **injected token provider**. For Drive, the token provider is simply the existing **`SecretResolver`** (`resolve("google_drive") -> access_token`); the operator wires `RefreshTokenSecretResolver` at the edge, the mocked slice injects a `MappingSecretResolver`. **No new token-provider type is needed** (unlike GitHub, which needed `InstallationTokenProvider`).
- **Layering**: keep the connector in `protocol/provider_acquisition/google_drive/` with a **local transport Protocol** (mirroring #180's `GitHubTransport`, status/json/headers) so `protocol/` does not import `runtime/`. **Recommendation (for /qor-plan):** factor the #180 `GitHubTransport`/`RecordedTransport` into a **shared `protocol/provider_acquisition/transport.py`** that both GitHub and Drive reuse (the two seams are identical) — or, if minimizing #180 churn, mirror it. Either way `screening.py` is shared as-is.
- **OAuth-refresh nuance**: refresh happens *inside* `RefreshTokenSecretResolver.resolve()` (operator-side, cached to `expires_in`). The connector only ever sees a resolved access token — so refresh imposes **no** extra seam on the discovery connector. The mocked slice never refreshes (the `MappingSecretResolver` returns a fixed placeholder).

## Blueprint Alignment

| ADR-0017 / issue claim | Actual finding | Status |
|---|---|---|
| `files.list` is "the critical-path build, currently deferred" (§Alpha scope) | confirmed deferred (`poll_specs.py:331`); this slice builds it | MATCH |
| `drive.metadata.readonly` NOT valid for `documents.get` (Finding 4) | confirmed (`poll_specs.py:334` + Google docs + action-needed fixture) | MATCH |
| Discovery returns descriptors/items, never authority objects; `create_provider_resource` absent | `.bicameral` folder *creation* correctly classified as egress/ProposedAction, out of scope | MATCH |
| Screening reuses one `adapter.core.sensitive` catalog (§3) | `screening.py` exists (on #180 branch); reused as-is | MATCH (pending #180 merge) |
| Mocked slice earns Beta; Live needs factory#93 | live `drives.list`/`files.list` blocked on factory#93 (open) | MATCH |

## Recommendations (for /qor-plan)

1. **Scope the listing to the product model**, not a generic browser: `list_resources` → shared drives (`drives.list`); `get_resource`/children → `.bicameral` project folders (`files.list` with `corpora=drive`+`driveId`+`supportsAllDrives`); `fetch_provider_item` → document leaf (reuse `parse_document` content, emit `ProviderItemEnvelope`).
2. **Reuse `SecretResolver` as the token provider** (no new type); inject `MappingSecretResolver` in tests. Keep a **local transport Protocol** to preserve `protocol`↛`runtime` layering.
3. **Factor or mirror the #180 transport seam**; reuse `screening.py` unchanged. Decide GitHub-transport-generalization vs Drive-local-mirror at plan time (note the #180-merge dependency).
4. **Recorded fixtures** under `protocol/provider_acquisition/fixtures/recorded/google_drive/` (so the existing secret-guard `rglob fixtures/**` covers them; the descriptor/item conformance glob targets only `descriptors/`+`items/`, so they won't be mis-validated) — drives.list page, files.list `.bicameral` + project folders + document, plus 401/403/404/400-stale/insufficient-scope cases.
5. **Map every F6 row to a recorded-response test**; the action-needed (missing-scope) case must reproduce the golden fixture's `required_scope`/`current_scope` shape.
6. **No `config.json` change**: scopes already declared; the `discovery` mode/block remains deferred to the ADR-0015 fan-out (same as #180 — connector-config `modes` enum is `webhook|active|passive`).

## Open Questions / risks

- **OQ1 (live blocker)**: live Drive API calls are blocked on **factory#93** (live Google connection baseline, OPEN). This slice is mocked/recorded only; live smoke deferred. Non-severe (documented fallback in the issue).
- **OQ2 (integration sequencing)**: `screening.py` lives on the **unmerged `feat/180` branch (PR #201)**. The #179 implement phase must either land after #180 merges to `dev`, or stack on `feat/180`. **Plan decision, not a research blocker.**
- **OQ3 (ledger fork)**: this research branch is off `origin/dev` (ledger head #214); #180 holds #215/#216 on its branch. This brief takes **#215 on this branch** — the `dev→main` integrator linearizes the two chains (as PR #182 did). Mechanical, expected under parallel governed branches.

## Updated Knowledge

Add to the connector-pattern doctrine: **the discovery transport/token seam is provider-agnostic** — GitHub needed a new `InstallationTokenProvider`, but Drive reuses the existing `SecretResolver`; the `RecordedTransport` + `screening.py` are shared. Future provider discovery slices should reuse, not re-derive, this seam. Captured as SG-2026-06-23-A in this brief's ledger entry.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor (/qor-plan next)._
