# Provider Acquisition Contract

**Status:** Proposed (pending bot **BicameralAI/bicameral-bot#405** sign-off)
**Decision record:** [ADR-0017](adr/0017-provider-acquisition-contract.md)
**Grounded by:** `docs/research-brief-source-acquisition-boundary-2026-06-16.md`
**Answers:** GH #173

The machine-facing contract surface for the **discovery / fetch / readiness** edge: how the bot (#405)
and the mcp UI discover provider resources, render a picker, and fetch a selected item — without
re-implementing provider mechanics and without integrations gaining canonical Bicameral authority. ADR-0017
records the *decision*; this document is the *contract* the consumers build against (the same split as
ADR-0015 ↔ `UI_RENDERING_SPEC.md`).

> **Proposed, not built.** No connector implements this surface yet (`SourceMode.DISCOVERY` is declared by
> 0/26 connectors today). The shape below is offered for the bot side to consume or counter; it is not
> final until cross-repo sign-off, and no field here should be treated as shipped.

## Boundary

`bicameral-integrations` returns **descriptors and provider-item envelopes (provider facts)**. It does
**not** return — and the schema forbids — any Bicameral authority object: `SourceBinding` approval, a
`Source`/`SourceSnapshot`/`SourceEvidence`/`DecisionCandidate` decision, `.bicameral` creation, or
event-store writes. Authority stays bot-side (ADR-0008). After receiving a descriptor or item, the bot
decides (separately, purpose-neutrally) whether a selected resource becomes a `SourceBinding` proposal,
captures fetched content into `Source`/`SourceSnapshot`/`SourceEvidence`, and routes later provider calls
back through `fetch_provider_item` using the descriptor's `resource_ref` (no re-discovery of identity).

## `ProviderResourceDescriptor`

Per-resource, runtime-discovered. Reuses `adapter.core.emissions.SourceRef` for the locator.

| Field | Type | Required | Notes |
|---|---|---|---|
| `resource_ref` | `SourceRef` | yes | `{source_id (=provider), ref (stable id), url, kind}`. Stable provider id, never the display name. |
| `display_name` | `str` | yes | Human picker label. |
| `resource_kind` | `str` | yes | `team`/`project`/`repository`/`folder`/`document`/`issue`/`pr`/`file`/… (mirrors `resource_ref.kind`). |
| `account_label` | `str` | yes | Connected account/workspace/org the resource was discovered under. |
| `parent` | `SourceRef \| None` | no | Parent locator for tree navigation. |
| `capabilities` | `frozenset[ResourceCapability]` | yes | What the current connection can do with this resource. |
| `permission_state` | `PermissionState` | yes | Usability of the resource under the current credential. |
| `action_needed` | `ActionNeeded \| None` | no | Present iff `permission_state != USABLE`. |
| `provider_metadata` | `dict` | no | Non-secret, round-trip data the connector needs to re-issue calls. Screened. |
| `etag` / `updated_at` | `str` | no | Provider freshness/debug markers when supplied. |

**Never present:** tokens, secrets, or any authority field. Enforced by the descriptor screen + schema.

## `ProviderItemEnvelope`

Returned when the bot fetches a selected leaf. Built from the **screened** `Observation` that
`fetch_provider_item` produces.

| Field | Type | Required | Notes |
|---|---|---|---|
| `resource_ref` | `SourceRef` | yes | The item's stable locator. |
| `item_kind` | `str` | yes | `issue`/`comment`/`document`/`file`/`pull_request`/… |
| `payload` | `str` | yes | Provider-normalized item content, **screened** through the same FX-SEC-001 path as every emission. |
| `item_url` | `str` | no | Provider web URL. |
| `author` / `timestamp` | `str` | no | Provider-supplied attribution when present (subject to the producer screen). |
| `cursor` / `freshness` | `str` | no | Refetch/paging marker. |
| `provider_metadata` | `dict` | no | Non-secret refetch data. Screened. |

## Enums

**`PermissionState`** — the usability of a resource under the current credential:

`USABLE`, `ACTION_NEEDED`, `INSUFFICIENT_SCOPE`, `NOT_FOUND`, `UNSUPPORTED`

**`ResourceCapability`** — provider-neutral, what a connection can do with a resource:

`READ`, `LIST_CHILDREN`, `CREATE_CHILD`, `FETCH_ITEMS`, `WRITE`

**Excluded vocabulary (by rule):** no capability or state token may name a Bicameral authority concept —
`Source`, `SourceBinding`, `Snapshot`, `candidate`. Those are bot-owned judgments, not provider facts.

`ActionNeeded`: `{reason: str (typed), hint: str}` — a connect/retry hint; carries no secret.

## Discovery outcome envelope

Every discovery operation returns a typed result envelope rather than raising or returning a bare value —
so a permission/access failure is a **first-class, screenable value**, not an exception that escapes the
funnel. Defined in `protocol/provider_acquisition/types.py` (introduced by PR #183 / issue #178; promoted
here per #185).

**`DiscoveryErrorKind`** — the typed reason a discovery operation could not succeed:

`PERMISSION_DENIED`, `ACTION_NEEDED`, `NOT_FOUND`, `UNSUPPORTED`, `PROVIDER_ERROR`

**`DiscoveryError`** — a structured failure (no secret, no provider exception object):

| Field | Type | Required | Meaning |
|---|---|---|---|
| `kind` | `DiscoveryErrorKind` | yes | Typed failure reason. |
| `message` | `str` | yes | Human-readable, non-secret summary. |
| `permission_state` | `PermissionState \| None` | no | The connection state that produced the failure, when known. |
| `action_hint` | `str \| None` | no | A connect/retry hint (mirrors `ActionNeeded.hint`); carries no secret. |

**`DiscoveryOutcome[T]`** — the generic result envelope wrapping any discovery return type `T`
(e.g. `ResourcePage`, `ProviderResourceDescriptor`, `AccessVerdict`, `list[Observation]`):

| Field | Type | Required | Meaning |
|---|---|---|---|
| `value` | `T \| None` | no | The success payload. |
| `error` | `DiscoveryError \| None` | no | The typed failure. |

**Invariant:** exactly one of `value` / `error` is populated; the `ok` property is
`error is None and value is not None`. An `INSUFFICIENT_SCOPE`/expired-grant result is returned as a
populated `error` (never an empty success) — the same "honest failure, never silent" discipline the
descriptor `permission_state` enforces.

## Operations (`DiscoveryConnector` Protocol)

```
list_resources(*, config, kind=None, parent=None, filters=None, cursor=None) -> ResourcePage
get_resource(ref)                                                            -> ProviderResourceDescriptor
validate_resource_access(ref, *, required: frozenset[ResourceCapability])    -> AccessVerdict
fetch_provider_item(ref, *, cursor_or_range=None)                            -> list[Observation]
```

- `ResourcePage`: `{items: tuple[ProviderResourceDescriptor, ...], next_cursor: str | None}`.
- `AccessVerdict`: `{permission_state, missing: frozenset[ResourceCapability], action_needed: ActionNeeded | None}`.
- `filters` reuses `adapter.core.filters.FilterSpec`; per-pull limits reuse `QuotaSpec`.
- `fetch_provider_item` returns `Observation`s so the caller funnels them through the existing
  `pipeline.normalize` → `validate_emissions` seam — discovery is **not** a second content path.
- **`create_provider_resource` is not on this Protocol.** A provider-safe create (e.g. a Drive folder) is
  proposed as a `ProposedAction` (ADR-0011); the bot governs and executes it. Integrations never writes.

## Security — one screen, every surface

- **Fetched item payloads** are screened by the same FX-SEC-001 chokepoint as emissions
  (`pipeline.validate_emissions` → `_screen_sensitive`, per-leaf `sensitive.detect_sensitive`,
  hard-reject secret/PHI/PAN). No unscreened pull path exists.
- **Descriptors / pages / verdicts** carry metadata, not content — but provider metadata is
  attacker-influenced (a folder named after a secret, a PAN-shaped label). A `screen_descriptor` helper
  runs the same per-leaf `detect_sensitive` over every string leaf (`display_name`, `account_label`,
  `provider_metadata` keys+values, `resource_ref.*`) before the descriptor crosses the boundary. Reuses
  the adapter catalog v1 — one detector, two entry points.
- **Secrets stay operator-side.** The live discovery HTTP call + credential resolution live in the
  operator runtime (`SecretResolver` by `source_id`); descriptors never carry tokens.

## Per-provider alpha resource kinds

| Provider | Discover (kinds) | Item leaf | Scopes / auth |
|---|---|---|---|
| **Linear** | `team` → `project` → `issue` | issue + comment thread | personal API key (raw `Authorization`). Workspace = `account_label`. |
| **Google Drive** | `folder`, `shared_drive` (via `files.list` — currently deferred, the critical-path build) + direct folder/doc URL entry | `document` | OAuth `drive.readonly` + `documents.readonly`. **`drive.metadata.readonly` is NOT valid for `documents.get`** (only the Drive `files.get` metadata path). |
| **GitHub** | `repository` (+ default branch) → `file`/`path`, `issue`, `pr` | file / issue / PR | webhook secret built; live-fetch auth model (PAT vs App installation token) **unbuilt — see open questions.** Installation/account = `account_label`. GitHub need not be an event substrate in the first slice. |

## Conformance fixtures (no live credentials)

A connector proves the contract offline with **golden pairs**: a recorded provider response →
expected `ProviderResourceDescriptor` (for `list_resources`/`get_resource`) and a recorded item response →
expected `ProviderItemEnvelope` (for `fetch_provider_item`). At least one Linear issue/comment path and
one GitHub-or-Drive evidence path. A passing fixture earns **Beta**; **Live** still requires operator
credentials + a real provider call (ADR-0012). A mock never promotes to Live.

## Open / cross-repo (not decided here)

1. **#405** confirms it consumes descriptors/items in this shape, or counters the field set.
2. GitHub live-fetch auth model — PAT vs GitHub App installation token — is unbuilt and unspecified.
3. Descriptor → bot-protocol/shared-schema promotion timing (integrations owns the mapping + pin and
   fails first on drift, mirroring the ADR-0015 / #42 Domain 4 contract).
