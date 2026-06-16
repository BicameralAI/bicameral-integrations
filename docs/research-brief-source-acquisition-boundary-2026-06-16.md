# Research Brief

**Date**: 2026-06-16
**Analyst**: The Qor-logic Analyst
**Target**: GH #173 — source acquisition boundary for Linear, Google Drive, GitHub (integrations side)
**Scope**: What "source acquisition" must cover per connector (auth/scopes, discovery/fetch surface, in-bounds vs out-of-bounds for integrations vs bot); the gap between the RFQ's candidate interfaces and what is built today; cross-reference with the merged #42 boundary position.

---

## Executive Summary

#173 asks integrations to define a **provider-neutral discovery/fetch/readiness contract** (a `ProviderResourceDescriptor` + provider item envelope, exposed via `list_resources` / `get_resource` / `validate_resource_access` / `fetch_provider_item` / `create_provider_resource`) so the bot can run a picker → select → fetch lifecycle without re-implementing provider mechanics. **The central finding is a structural gap, not a drift:** the repo today is built entirely as an **ingest funnel** (push: webhook/poll → `Observation` → `AdapterEmission` → gateway), and exposes **no discovery/pull surface at all**. A grep for every candidate interface name in #173 returns zero files. The enum slot `SourceMode.DISCOVERY` exists (`adapter/core/capabilities.py:15`) but **no connector declares it**, and `SourceCapabilities` carries three latent, unused flags (`supports_filters`, `supports_resource_overrides`, `source_specific_filters`) — the architecture *anticipated* discovery but never built it. #42 (merged position `docs/rfq-bot-integrations-boundary-2026-06-06.md`, PR #69) is **complementary, not overlapping**: it settled the *evidence-ingest/egress/identity/schema/preflight* boundary; #173 is the *acquisition (pre-ingest)* boundary that feeds it. The two share one principle — **integrations is the expressive edge, the bot is the authority** — and #173's descriptor/item envelope are the discovery-side analogue of #42's `AdapterEmission`/`IngestRequest`.

## Findings

### 1. The discovery/pull surface does not exist — the repo is an ingest funnel only

- Grep for `list_resources|get_resource|fetch_provider_item|validate_resource_access|create_provider_resource|ProviderResourceDescriptor|resource_kind|permission_state` → **no files found** (entire tree).
- Every connector's public surface is ingest-shaped (`connectors/<id>/connector.py`):
  - `observations(payload) -> list[Observation]` — parse a *delivered* payload.
  - `verify()` / `normalize_event()` — webhook signature + dedup (push path).
  - `parse_*` free functions — provider-neutral parse into one `Observation`.
  - `can_handle_ref(ref)` — route a *known* ref (github `connector.py:106`, google_drive `connector.py:168`); host-pinned, not a discovery call.
  - `capabilities: SourceCapabilities(modes=...)`.
- The "fetch half" (`runtime/poll_client.py`, `poll_auth.py`, `poll_specs.py`, `graphql_poll.py`, `doc_fetch.py`, FX-RUNTIME-003) fetches a **known** resource by cursor/URL/id — it does **not** list or discover. e.g. `doc_fetch` does `documents.get` on a known document id; Linear `graphql_poll` pages issues by Relay cursor; GitHub has **no live fetch** at all.

**Implication:** #173 is a **net-new surface**, not an adaptation of an existing one. It is orthogonal to the ingest funnel and must not be force-fit into `Observation`/`AdapterEmission` (those are *evidence* shapes; a descriptor is a *picker/locator* shape, not screened evidence content).

### 2. Latent scaffolding already exists for it

- `adapter/core/capabilities.py:9-16` — `SourceMode` already has `DISCOVERY = "discovery"`. **Zero connectors declare it** (confirmed `grep -rl DISCOVERY connectors/` → NONE; all 26 declare only `active`/`passive`/`webhook`).
- `adapter/core/capabilities.py:18-29` — `SourceCapabilities` already carries `supports_filters`, `supports_quotas`, `supports_resource_overrides`, `source_specific_filters` — used by **no** connector (all pass `modes=` only). These map almost 1:1 onto #173's `capabilities` (`list_children`, `create_child`, `fetch_items`, filters).

**Implication:** the descriptor contract can extend an existing capability vocabulary rather than invent one. Recommend `SourceMode.DISCOVERY` become the declared mode that gates whether a connector exposes `list_resources`/`get_resource`.

### 3. The word "descriptor" is already overloaded — keep #173 distinct from ADR-0015

- The existing "descriptor" in this repo is the **connector config descriptor** (FX-CFG-001 / ADR-0015 / sealed #116): `connectors/<id>/config.json` — a *per-connector, static* declaration of credentials, modes, runtime_config, webhook setup (see `connectors/linear/config.json`). It drives the **mcp config UI** (which fields the operator must supply to connect).
- #173's `ProviderResourceDescriptor` is a *per-resource, runtime-discovered* object (this specific Linear team, this Drive folder, this GitHub repo) used to render a **resource picker** after connection.

**Implication (naming drift risk):** do **not** reuse "descriptor" unqualified. Recommend the names **`ConnectorConfigDescriptor`** (existing, ADR-0015) vs **`ProviderResourceDescriptor`** (new, #173). Config descriptor = "how to connect"; resource descriptor = "what you can pick once connected."

### 4. Per-connector acquisition reality (auth/scope/discovery/fetch)

#### Linear (`connectors/linear/`)
- **Built**: webhook parse (`parse_event`, `connector.py:33`) + active GraphQL issue fetch (`parse_issue_node`, `connector.py:66`, driven by `runtime.graphql_poll`).
- **Auth** (`config.json`): personal API key `^lin_api_[A-Za-z0-9]+$`, raw `Authorization` header (no Bearer); webhook signing secret (`Linear-Signature`, hex HMAC-SHA256 + 60 s anti-replay).
- **Discovery gap**: no workspace/team/project enumeration. The GraphQL endpoint that fetches issues could also query `teams`/`projects`/`viewer`, but no such call exists.
- **Alpha-first resources (Q4)**: `team` (the natural binding scope) → `project` → `issue` (+ comment thread as the item). Workspace is the `account_label`, not a pickable child for alpha.

#### Google Drive (`connectors/google_drive/`)
- **Built**: pure parse surface for a `documents.get` response (`parse_document`, `connector.py:131`); doc-id extracted from a Docs/Drive URL (`parse_gdrive_url`, `connector.py:29`). Live call lives in `runtime.doc_fetch`.
- **Auth/scopes** (`references.md`, verified 2026-06-08): OAuth `documents.readonly` + `drive.readonly`/`drive.file`. **`drive.metadata.readonly` is NOT valid for `documents.get`** — only for the Drive `files.get` metadata path. OAuth refresh is **deferred** (operator-runtime).
- **Discovery gap (largest)**: `files.list` folder/shared-drive discovery is **explicitly deferred** (connector docstring `connector.py:6-9` + `references.md`). This is *exactly* the discovery surface #173 needs for a folder/doc picker. Alpha Drive ingestion of a folder is impossible without it.
- **Alpha-first resources (Q5)**: `folder` + `shared drive` enumeration (`files.list`), `document` leaf, plus **direct folder/doc URL entry** (already half-built via `parse_gdrive_url`) as the cheapest first slice that needs no `files.list`.

#### GitHub (`connectors/github/`)
- **Built**: parse surface only (`parse_pull_request`, `connector.py:48`) + webhook verify (`X-Hub-Signature-256`). **No live REST/GraphQL fetch** (deferred, `connector.py:82-87`).
- **Auth**: webhook secret (HMAC). Live fetch auth (PAT vs GitHub App installation token) is **undecided/unbuilt** — material for Q6/Q9.
- **Discovery gap**: no repo/issue/PR/file enumeration.
- **Alpha-first resources (Q6)**: `repository` (+ `default branch`) → `file`/`path` and `issue`/`PR` as items. Installation/account scope is the `account_label`. #173 itself notes GitHub need not become an event substrate in the first slice.

### 5. Direct answers to #173's 11 questions (integrations position)

1. **Common descriptor fields**: adopt #173's field hints verbatim as the v0 `ProviderResourceDescriptor` — `provider, resource_id, resource_kind, display_name, web_url, parent, account_label, capabilities[], permission_state, action_needed?, provider_metadata, etag/updated_at?`. All non-secret, all locator/picker data.
2. **Provider item envelope**: `{provider, resource_ref, item_id, item_kind, payload (provider-normalized, screened), item_url, author?, timestamp?, freshness/cursor, provider_metadata}`. **Reuse the FX-SEC-001 screen** (`adapter/core/pipeline.py validate_emissions` / `redact`) on the `payload` before return — a fetched item is the same leak surface as an emission excerpt.
3. **Safe capability names**: `read, list_children, create_child, fetch_items, write` (provider-neutral). **Too bot-specific**: anything naming `Source`/`SourceBinding`/`Snapshot`/`candidate` — those are bot authority terms and must not appear in a capability flag. Map onto the existing `SourceCapabilities` flags (Finding 2).
4. **Linear first**: team → project → issue(+comments). (Finding 4.)
5. **Drive first**: folder + shared drive via `files.list`, document leaf, plus direct URL entry. (Finding 4 — `files.list` is the blocking dependency.)
6. **GitHub first**: repository(+default branch) → file/path, issue, PR. (Finding 4.)
7. **Sufficient-for-substrate data without integrations creating `.bicameral`**: the descriptor's `resource_kind` + `capabilities` + `permission_state` + `provider_metadata` let the bot judge substrate readiness; integrations returns *facts about the resource*, never a substrate decision, never `.bicameral` I/O (consistent with #42's ADR-0008 authority split).
8. **Purpose-neutrality**: descriptors carry **no** `SourceBinding`/`Source` field; the bot separately interprets a descriptor as a binding candidate. Enforce by schema (no authority fields permitted) — same discipline as #42's "integrations cannot construct a T4 object."
9. **Scopes + typed action-needed**: per-provider scope set (Drive: `documents.readonly`+`drive.readonly`; Linear: API key; GitHub: TBD PAT vs App). Missing/insufficient → `permission_state ∈ {usable, action_needed, insufficient_scope, not_found, unsupported}` + typed `action_needed` with a connect/retry hint. This is the discovery-side analogue of #42's typed-failure ownership.
10. **Promote to bot shared schema?**: yes — **after** the integrations contract is proven on fixtures (mirror #42 Domain 4: integrations owns the mapping + a vendored/pinned schema; promote stable fields into bot protocol once a conformance fixture passes both sides).
11. **Fixtures without live creds**: recorded `list_resources`/`get_resource`/`fetch_provider_item` responses per provider → golden `ProviderResourceDescriptor` / item-envelope pairs, asserted offline (the established connector fixture pattern; FX-RUNTIME-003 proved fetch on recorded fixtures — same approach). A fixture pass is **Beta**, not Live (ADR-0012).

## Blueprint Alignment

| #173 candidate claim / interface | Actual finding (file:line) | Status |
|---|---|---|
| `list_resources(provider, cursor, filters)` exists/expected | No discovery method anywhere (grep: 0 files) | **DRIFT (gap)** — net-new |
| `get_resource` / `fetch_provider_item` / `validate_resource_access` | Only ingest `observations()`/`parse_*` + known-ref fetch-half | **DRIFT (gap)** |
| `create_provider_resource` (Drive folder) | No create surface; integrations is read-only (ADR-0008) | **DRIFT (gap)** — needs explicit ADR-0008 carve-out for provider-safe create |
| Discovery is a recognized mode | `SourceMode.DISCOVERY` defined (`capabilities.py:15`), declared by 0 connectors | **PARTIAL** — slot exists, unbuilt |
| `capabilities[]` (list_children/create_child/fetch_items) | `SourceCapabilities` latent flags `supports_filters/_resource_overrides/source_specific_filters` unused (`capabilities.py:23-26`) | **PARTIAL** — vocabulary exists |
| `ProviderResourceDescriptor` (per-resource) | Only `config.json` connector-config descriptor (ADR-0015) — per-connector, static | **DRIFT (naming)** — distinct object |
| Drive folder discovery for alpha ingestion | `files.list` explicitly deferred (`google_drive/connector.py:6-9`, `references.md`) | **DRIFT (gap)** — blocks alpha Drive |
| GitHub provider-item fetch | No live GitHub fetch (deferred, `github/connector.py:82-87`) | **DRIFT (gap)** |
| Boundary already settled by #42 | #42 (PR #69 merged) covers ingest/egress/identity/schema/preflight, NOT acquisition/discovery | **MATCH (complementary)** — no overlap |

## Recommendations

1. **(P1, ADR)** Author a new ADR — *Provider Acquisition Contract* — defining `ProviderResourceDescriptor` + provider item envelope as the discovery-side analogue of #42's emission/envelope. Adopt #173's field hints as v0. This is the RFQ answer artifact #173 asks for. (Pairs with the merged #42 doc; reference it explicitly.)
2. **(P1, naming)** Lock the two-descriptor vocabulary: `ConnectorConfigDescriptor` (ADR-0015, existing) vs `ProviderResourceDescriptor` (new). Prevents drift against the sealed config-descriptor contract.
3. **(P1, ADR-0008 carve-out)** #173's `create_provider_resource` (Drive folder) is the **first write integrations would own**. ADR-0008 currently makes integrations read-only. Either carve out an explicit "provider-safe, non-authority create" exception or route create through the bot's egress/`ProposedAction` lane (#42 Domain 2). **Recommend: route through `ProposedAction`** to keep ADR-0008 intact — surface to operator before deciding.
4. **(P2, build order)** Drive `files.list` folder discovery is the **critical-path dependency** for alpha Drive ingestion and the cleanest first `list_resources` implementation. Sequence after the ADR, ahead of GitHub live fetch.
5. **(P2, reuse)** Declare `SourceMode.DISCOVERY` on connectors that gain a discovery surface; map #173 capabilities onto the existing `SourceCapabilities` flags rather than a parallel vocabulary.
6. **(P2, security)** Run the FX-SEC-001 screen (`validate_emissions`/`redact`) on every `fetch_provider_item` payload — a fetched item is the same leak surface as an emission excerpt; do not let the pull path bypass the producer screen.
7. **(P3, fixtures/CI)** Add recorded golden descriptor + item-envelope fixtures per provider (offline, FX-RUNTIME-003 pattern); a pass earns Beta, not Live (ADR-0012).
8. **(governance)** This is an **RFQ answer, not implementation** (#173 Non-Goals + `agent-task` excluded). Do not open implementation tickets until Kevin/Jin + the bot-side #405/#386/#390 agree — mirror #42's "follow-ups only after sign-off."

## Updated Knowledge

For `docs/SHADOW_GENOME.md` (new shadow-genome lesson candidate):

- **SG-2026-06-16-A (architecture asymmetry, discovery edge):** the platform is an *ingest funnel* (push: provider → `Observation` → emission). It has **no pull/discovery surface**; the `SourceMode.DISCOVERY` enum slot and `SourceCapabilities` filter/override flags are latent and unbuilt. Any "let the user browse & pick a provider resource" feature (#173) is net-new and must not be conflated with the ingest path or with the ADR-0015 connector-config descriptor.
- **Naming hazard:** "descriptor" is overloaded — `config.json` is the *connector-config* descriptor (ADR-0015); #173's is the *provider-resource* descriptor. Qualify the term in all new artifacts.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor. This is an RFQ answer (#173); no implementation is authorized until the cross-repo boundary is signed off._
