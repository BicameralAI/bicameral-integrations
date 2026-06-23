# ADR-0017: Provider acquisition contract (the discovery/fetch/readiness edge)

**Date:** 2026-06-16
**Status:** Proposed (RFQ answer to GH #173; not Accepted until cross-repo sign-off — Kevin/Jin + bot #405/#386/#390)
**Level:** L2 (declares a new connector surface + auth/permission semantics consumed cross-repo)
**Relates to:** ADR-0004 (adapter boundary / ingest funnel), ADR-0005 (emission contract), ADR-0006 (active/passive/webhook modes), ADR-0008 (integrations are evidence adapters, not state authorities), ADR-0009 (trust-tiered governance), ADR-0011 (proposed-action / review-evidence), ADR-0012 (readiness ladder + operator runtime), ADR-0015 (config descriptor contract)
**Grounded by:** `docs/research-brief-source-acquisition-boundary-2026-06-16.md` (META_LEDGER #201)

## Context

Until now the connector/adapter side was **deliberately minimized** — held thin while the mcp repo
took shape so the UI's data needs would drive the contract, not the reverse. The repo is therefore an
**ingest funnel only** (ADR-0004): every connector parses a *delivered or already-located* payload
(webhook event, polled page, fetched URL/id) into one neutral `Observation`, which funnels through the
single `adapter.core.pipeline.normalize` seam → `AdapterEmission` → the bot gateway. There is **no
pull/discovery surface**: a grep for `list_resources` / `get_resource` / `fetch_provider_item` /
`validate_resource_access` / `create_provider_resource` / `ProviderResourceDescriptor` returns zero
files (research brief, Finding 1).

GH #173 (coordinated with bot #405) now asks integrations to supply that greater structure: a
**provider-neutral discovery/fetch/readiness contract** so the bot can run a *connect → browse → pick →
fetch* lifecycle (an operator picker over Linear, Google Drive, and GitHub resources) without
re-implementing provider mechanics and without gaining canonical Bicameral authority. Because this is
the first net-new connector surface since the freeze, the contract must be designed for the **entire
ecosystem** (26 connectors today; T0–T3; active/passive/webhook) and the **universal adapter**, so
discovery stays consistent and secure with the existing ingest funnel rather than becoming a parallel,
unscreened side-channel.

Two pieces of latent scaffolding already anticipate this and are adopted rather than reinvented:
`adapter/core/capabilities.py` defines `SourceMode.DISCOVERY` (declared by 0/26 connectors today), and
`SourceCapabilities` carries unused `supports_filters` / `supports_quotas` /
`supports_resource_overrides` / `source_specific_filters` flags. `adapter/core/filters.py` already
defines `FilterSpec` + `QuotaSpec`.

## Decision

Add a **fourth connector surface** — *discovery* — alongside the three ingest modes, as a peer
Protocol in the universal adapter, gated on the existing `SourceMode.DISCOVERY`. Discovery is **opt-in
per connector**: a connector that does not implement it is unaffected, and the existing
operator-supplied-ref / URL-entry path (`can_handle_ref`, `parse_gdrive_url`) remains the fallback.
Integrations returns **descriptors and provider-item envelopes (facts)**, never Bicameral authority
objects.

### 1. Protocol — extend `adapter/core/contracts.py`

A new `DiscoveryConnector(Connector, Protocol)` peer to `ActiveConnector`/`PollingConnector`/
`WebhookConnector`:

```python
class DiscoveryConnector(Connector, Protocol):
    """Operator-driven provider resource discovery and selected-item fetch.

    Purpose-neutral: returns descriptors/items (provider facts), never a
    Bicameral Source/SourceBinding/Snapshot decision (ADR-0008).
    """

    def list_resources(
        self, *, config: dict, kind: str | None = None,
        parent: SourceRef | None = None, filters: FilterSpec | None = None,
        cursor: str | None = None,
    ) -> ResourcePage: ...

    def get_resource(self, ref: SourceRef) -> ProviderResourceDescriptor: ...

    def validate_resource_access(
        self, ref: SourceRef, *, required: frozenset[ResourceCapability],
    ) -> AccessVerdict: ...

    def fetch_provider_item(
        self, ref: SourceRef, *, cursor_or_range: str | None = None,
    ) -> list[Observation]: ...
```

- `fetch_provider_item` returns **`Observation`s** — i.e. it feeds the *same* `normalize` →
  `validate_emissions` funnel as every other ingest path (Security §3). A fetched item is evidence; it
  must not be a second, unscreened content path.
- `list_resources` / `get_resource` / `validate_resource_access` return **descriptors / verdicts**,
  not content — non-secret locator metadata only (Security §3).
- `create_provider_resource` is **not** on this Protocol — it is a write and is handled by §4.

### 2. Neutral objects — new `adapter/core/discovery.py`

Frozen dataclasses, consistent with `emissions.py` (`SourceRef`/`Observation` reused, not duplicated):

- `class PermissionState(StrEnum)`: `USABLE, ACTION_NEEDED, INSUFFICIENT_SCOPE, NOT_FOUND, UNSUPPORTED`.
- `class ResourceCapability(StrEnum)`: `READ, LIST_CHILDREN, CREATE_CHILD, FETCH_ITEMS, WRITE` —
  provider-neutral; **no** Bicameral-authority term (`Source`, `SourceBinding`, `Snapshot`,
  `candidate`) may appear in this vocabulary (purpose-neutrality, ADR-0008).
- `ProviderResourceDescriptor`: `resource_ref: SourceRef` (carries `source_id`/provider, `ref`=stable
  id, `url`, `kind`), `display_name`, `account_label`, `parent: SourceRef | None`,
  `capabilities: frozenset[ResourceCapability]`, `permission_state: PermissionState`,
  `action_needed: ActionNeeded | None`, `provider_metadata: dict` (non-secret, round-trip data),
  `etag`/`updated_at` (optional freshness).
- `ProviderItemEnvelope` (the typed return of a fetched leaf, built from the screened `Observation` +
  freshness): `resource_ref`, `item_kind`, `payload` (provider-normalized, **screened**),
  `item_url`, `author`/`timestamp` (optional), `cursor`/`freshness`, `provider_metadata`.
- `ResourcePage`: `items: tuple[ProviderResourceDescriptor, ...]`, `next_cursor: str | None`.
- `AccessVerdict`: `permission_state`, `missing: frozenset[ResourceCapability]`,
  `action_needed: ActionNeeded | None`.
- `ActionNeeded`: `reason` (typed), `hint` (connect/retry), no secret.

**Naming discipline (research brief, Finding 3):** "descriptor" is now two distinct objects — the
ADR-0015 **`ConnectorConfigDescriptor`** (`connectors/<id>/config.json`, per-connector, static, "how
to connect") and this ADR's **`ProviderResourceDescriptor`** (per-resource, runtime-discovered, "what
to pick once connected"). They must never be conflated in code or docs.

### 3. Security — one screen, every surface (extends FX-SEC-001, not a side-channel)

The ingest funnel's security rests on a **single chokepoint**: `pipeline.validate_emissions` →
`_screen_sensitive`, which scans every wire-bound field **per leaf** with `sensitive.detect_sensitive`
(HARD-rejects secret/PHI/PAN). Discovery must inherit this, not bypass it:

- **Fetched items** — `fetch_provider_item` returns `Observation`s and the caller funnels them through
  `normalize` → `validate_emissions` (the *same* FX-SEC-001 screen). No item content reaches a mod or
  the gateway unscreened. (A fetched Drive doc / GitHub file is exactly the leak surface an emission
  excerpt is — research brief, Recommendation 6.)
- **Descriptors / pages / verdicts** — these carry *metadata*, not content, but provider metadata is
  attacker-influenced (a folder named after a secret, a PAN-shaped display name). A
  **`screen_descriptor`** helper in `discovery.py` runs the same per-leaf `detect_sensitive` over every
  string leaf of a descriptor (`display_name`, `account_label`, `provider_metadata` keys+values,
  `resource_ref.*`) before it crosses the boundary — fail-closed, mirroring `_metadata_strings`. The
  schema additionally **forbids** any secret-bearing or authority-bearing field by construction.
- **Reuse, do not fork** — `screen_descriptor` calls `sensitive.detect_sensitive` directly (the
  adapter's existing catalog v1); it does not reimplement detection. One catalog, two entry points
  (emission screen + descriptor screen).
- **Auth/secrets stay operator-side** — as with poll/active (ADR-0012), the live discovery HTTP call
  and credential resolution live in the operator runtime (`SecretResolver` by `source_id`); the
  connector is a pure parse/shape surface. Descriptors never carry tokens.

### 4. Authority boundary — `create_provider_resource` routes through ProposedAction (ADR-0008 intact)

`create_provider_resource` (e.g. a Drive folder, where provider-safe) is the **first write integrations
would own** and directly tensions ADR-0008's read-only stance. Rather than carve a write exception into
the discovery Protocol, it is modeled as a **`ProposedAction`** (ADR-0011 / #42 Domain 2): integrations
*proposes* the create with `{intent, target parent ref, kind, name}`; the bot governs and executes it
as `Egress`; integrations holds no approval/execution/retry state. This keeps ADR-0008 ("evidence
adapters, not state authorities") unbroken — integrations still emits proposals, never mutations.

### 5. Config descriptor integration (ADR-0015)

A discovery-capable connector declares `"discovery"` in its `config.json` `modes` (the validator's
`modes ⊆ capabilities.modes` drift-guard already enforces consistency) and adds a per-`resource_kind`
capability matrix + required scopes under a new optional `discovery` block (e.g. Drive:
`folder`/`shared_drive`/`document` kinds; scopes `drive.readonly`+`documents.readonly` — note
`drive.metadata.readonly` is **not** valid for `documents.get`, research brief Finding 4). The
`connector-config.schema.json` gains the optional block (additive; fail-closed unknown-key rule holds).

### 6. Trust tiers & readiness (ADR-0009 / ADR-0012)

- Discovery respects trust tier: T0 local/dev connectors (aider, claude_code, local_directory, sarif,
  continue_dev) and evidence-only connectors need no discovery and declare none. Discovery is for
  connectors with a browsable provider account (Linear T1, Google Drive T1/T3, GitHub T1).
- Readiness ladder unchanged: a discovery surface proven on **recorded fixtures** (golden descriptor /
  item-envelope pairs, offline, FX-RUNTIME-003 pattern) earns **Beta**; **Live** requires operator
  credentials + a real provider call (ADR-0012). A mock never promotes to Live.

### 7. Promotion to shared schema (mirrors #42 Domain 4)

Integrations owns the descriptor/item shape and a vendored/pinned copy; once a cross-repo conformance
fixture passes both sides, the stable fields are proposed into bot protocol/shared schema. Integrations
fails first on drift (it owns the mapping + pin).

### Alpha scope (per-provider first slice)

- **Linear:** `team` → `project` → `issue` (+comment thread as the item). Workspace = `account_label`.
- **Google Drive:** `folder` + `shared_drive` discovery (**`files.list` — the critical-path build**,
  currently deferred), `document` leaf, plus direct folder/doc URL entry (already half-built via
  `parse_gdrive_url`) as the zero-`files.list` first step.
- **GitHub:** `repository` (+default branch) → `file`/`path`, `issue`, `PR`. Installation/account =
  `account_label`. GitHub need not become an event substrate in the first slice (#173).

## Consequences

- The bot can render a resource picker and fetch selected items against a typed, screened,
  purpose-neutral contract — without provider mechanics leaking into the bot or authority leaking into
  integrations.
- Discovery is a first-class peer of the ingest funnel sharing **one** security chokepoint, not a
  parallel unscreened path. The "N surfaces → 1 screen" invariant (ADR-0004) is preserved for pull as
  it is for push.
- The change is additive and opt-in: the 26 existing connectors are untouched until each opts into
  `SourceMode.DISCOVERY`; the config schema gains one optional block; `governance_gate.py` (portable,
  cross-repo) is **not** touched (the discovery validator, like ADR-0015's, is a repo-local `ci.yml`
  step).
- `create_provider_resource` introduces no new authority: it is a `ProposedAction`, governed/executed
  bot-side.
- **Open / cross-repo (not decided here):** bot #405 must confirm it consumes descriptors/items in
  this shape; the descriptor→shared-schema promotion. **The GitHub live-fetch auth model is now decided —
  see Addendum 2026-06-23 (#180).**

## Alternatives considered

- **Model discovery as another ingest mode (reuse `pull`/`fetch_active`)** — rejected: those return
  `Observation` *content*; discovery's `list_resources`/`get_resource` return *locator descriptors*
  with capability/permission state. Overloading the ingest Protocols would blur content vs locator and
  the security screen (descriptors need a descriptor screen, not the emission screen).
- **A parallel "discovery service" outside the universal adapter** — rejected: it would create a second
  content path that bypasses the single FX-SEC-001 chokepoint — the exact side-channel this ADR exists
  to prevent.
- **Let integrations own `Source`/`SourceBinding` creation directly** — rejected: violates ADR-0008;
  #173 explicitly excludes it.
- **Give `create_provider_resource` a write exception on the discovery Protocol** — rejected in favor
  of `ProposedAction` routing, which keeps ADR-0008 read-only and reuses the governed egress lifecycle.
- **Reuse "descriptor" unqualified for both config and resource** — rejected: it is the documented
  naming hazard (research brief Finding 3); the two objects are qualified.

## Addendum 2026-06-23 (#180): GitHub live discovery/fetch auth model — DECIDED

Resolving the Consequences open question for GitHub (owner decision on #173):

- **GitHub App installation auth ONLY.** Live GitHub discovery/fetch authenticates as a GitHub App
  **installation**, using a short-lived installation access token. **PAT / imported-token fallback is
  rejected for alpha live fetch** — there is no PAT code path by construction.
- **Hosted credential boundary.** The GitHub App private key / client secret are brokered hosted-side
  (the installation token broker, BicameralAI/bicameral-cloud#7); the integrations connector receives
  only the resolved installation token via an injected `InstallationTokenProvider` and never sees the
  App private key. Tokens never appear in descriptors, fixtures, logs, schemas, or error messages
  (token-free `DiscoveryError`, mirroring `poll_auth.PollError`).
- **Mocked/recorded slice built; live deferred.** `protocol/provider_acquisition/github/`
  (`GitHubDiscoveryConnector` over an injected transport + token provider) implements
  list/get/validate/fetch against **recorded** GitHub REST responses
  (`fixtures/recorded/github/*.json`, secret-guard-covered). The live `urllib` transport is deferred to
  cloud#7 — a mock never promotes to Live (§6). Descriptor/item screening reuses the single
  `adapter.core.sensitive` catalog via `protocol/provider_acquisition/screening.py` (§3; shared with the
  Drive slice #179). `create_provider_resource` remains absent (§4 / ADR-0008).
- **Config-descriptor block deferred.** §5's `discovery` block in `connectors/github/config.json` is
  **not** added here: the `connector-config.schema.json` `modes` enum is `webhook|active|passive`, so a
  `discovery` mode + block is an additive ADR-0015 config-contract change owned by that fan-out, not #180.
