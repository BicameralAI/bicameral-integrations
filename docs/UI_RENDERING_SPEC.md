# Connector + Mod Config — UI Rendering Spec (for the mcp repo)

**Status:** Reference spec (v1 connectors 2026-06-08; **v1 mods 2026-06-13**). **This is a contract for the mcp UI team, not code.**

> **Two descriptor families, one cohesive UI.** This repo ships a UI data contract for BOTH **connectors**
> (`connectors/<id>/config.json` + `connectors/index.json`, schema `connectors/_schema/connector-config.schema.json`)
> AND **mods** (`mods/<id>/config.json` + `mods/index.json`, schema `mods/_schema/mod-descriptor.schema.json`). The
> connector sections below render the "connect a source" flow; the **Mods** section at the foot renders the
> "enable advisory mods" flow. Together they give the frontend everything to build one cohesive
> sources-and-mods UI. Both are kept schema-valid + code-consistent in CI
> (`scripts/validate_connector_config.py`, `scripts/validate_mod_config.py`).

**Tracked in:** [BicameralAI/bicameral-mcp#572](https://github.com/BicameralAI/bicameral-mcp/issues/572)
— the mcp work item to render the **Linear + Google Drive** connector config UI against this spec.

`bicameral-integrations` ships the **data contract** — a per-connector `connectors/<id>/config.json`
(schema: `connectors/_schema/connector-config.schema.json`) and an aggregated `connectors/index.json`.
The **mcp repo renders it**. This repo holds no UI code and no secret values. This spec defines how each
field and each `instructions[]` action should render so the two repos agree.

## Boundary

| `bicameral-integrations` (this repo) | `mcp` repo |
|---|---|
| `config.json` × N + JSON Schema + `index.json` + validator | imports `index.json`; renders config UI |
| declares **requirements** (credentials, scopes, knobs, steps) | collects **values** (secrets, tokens) |
| stdlib-only, zero UI deps | owns all rendering + OAuth client + secret storage UX |

The integrations repo **never** sees a secret value — secrets resolve at the operator runtime via
`SecretResolver`. The UI collects them and hands them to that runtime, not to this repo.

## Connector card

Render from `index.json`. Use **`available`** (boolean) as the canonical "show as available vs
coming-soon" flag — NOT `status`/`live_readiness` (those can disagree; `available` is the single source).
Card: `name`, `description`, `icon?`, `category`, `trust_tier`, a `status` chip.

## The config-on-rails wizard (`instructions[]`)

Render the ordered `instructions[]` as a stepper. Switch on `action`:

| action | Render |
|---|---|
| `open_url` | A link/button to `link`; instructive `text`. (`ref` cites the verified source — for QA, not display.) |
| `paste_secret` | A **masked** input bound to the matching `credentials[]` entry; apply `credentials[].validation` (regex) to catch paste errors (e.g. a `Bearer`-prefixed key where a raw key is required). |
| `oauth_consent` | A **"Connect with `<provider>`"** button that launches the OAuth client for the credential's `scopes`. The UI owns the consent flow; **token exchange + refresh are the operator runtime's job** (the credential carries `refresh_owner: "operator"`, `wiring_oversight: true`). |
| `register_webhook` | Show the operator's **`webhook.receiver` URL** (operator-provisioned — the UI fills the value) as a **copyable** field, plus a copyable **signing-secret** panel; `text`+`link` guide the operator to register it at the provider. |
| `configure` | A typed input per relevant `runtime_config[]` entry (label, default, required). |
| `verify` | A **"Test connection"** button that drives the operator runtime's recorded-transport/live harness and shows pass/fail. |

## Credentials (`credentials[]`)

One control per entry, by `type`: `api_key` → masked text (+ `header` hint, `validation`);
`webhook_secret` → masked text; `basic` → user+password; `oauth2` → the consent button (above) with the
`scopes` shown as a permissions disclosure. A connector may declare **multiple** credentials (e.g. Linear
= `api_key` + `webhook_secret`); render all required ones. Heed `wire_gates[]` — if a credential's wiring
is gated (e.g. the Linear two-secret resolver gap), surface the note to the operator.

## Permissions / data disclosure (`data`) — trust-disclosure surface

Show `data.emits`, `data.pii_posture`, OAuth `scopes`, and `trust_tier` as a "what this connector can see
/ emit" panel before the operator connects — the transparency surface.

**`data.pii_posture`** is the canonical trust-disclosure surface for connectors: it tells the operator
exactly what PII the connector can see and how it is handled. UI implementations should render
`pii_posture` prominently (e.g. as an expandable "What this connector can see" panel) so operators make
an informed decision before connecting. The mod analogue is `em_safe.forbidden_actions` (see Mods
section below).

## Ingestion Gate display hints (`ingestion_gate`)

Optional per-connector object providing source-specific display metadata for the Ingestion Gate UI.
These hints are **presentational only** — they let the dashboard render source evidence rows with
connector-appropriate labels and empty states. **Bot-owned governance still controls all review
actions** (accept, reject, promote); the `ingestion_gate` object contains no review commands, signoff
states, compliance states, or Decision authority.

| Field | Render |
|---|---|
| `source_title_template` | Title for the source row; `{field_name}` placeholders are filled from adapter-emitted fields. |
| `source_type_label` | Short noun (e.g. "Slack message", "Devin session") for the evidence kind badge. |
| `summary_fields` | Ordered list of adapter-emitted field names shown in the evidence summary row. |
| `evidence_labels` | Map of evidence-kind keys (matching `data.emits` entries) to human display labels. |
| `empty_state` | Message shown when no evidence from this source has been ingested yet. |

Not every connector will declare `ingestion_gate` — the field is optional in the schema. When absent,
the UI should fall back to generic evidence rendering.

## References & gates

Render `references[]` as doc links; render `wire_gates[]` + `live_readiness` as a pre-go-live checklist
the operator must clear (these are the "not yet confirmed against live" items).

## Versioning

The schema's `$id` versions the contract. Breaking field changes bump it; the mcp repo pins a schema
version. The validator (`scripts/validate_connector_config.py`) keeps every descriptor + the index in
sync in CI, so what the UI imports is always schema-valid and code-consistent.

---

# Mods — UI Rendering Spec

`bicameral-integrations` ships the **mod data contract** — a per-mod `mods/<id>/config.json`
(schema: `mods/_schema/mod-descriptor.schema.json`) + an aggregated `mods/index.json` + a generated
`mods/<id>/SETUP.md`. The **mcp repo renders it**. A mod has **no credentials and no live network** — it is
an advisory post-processor over the neutral evidence stream (ADR-0008/0013), so the mod UI is an
**enable/configure + disclose** surface, not a "connect with secrets" wizard.

## Mod card

Render from `mods/index.json`. Card: `name`, `description`, `icon?`, `family` (group/sort by it), the
**`version`**, and — always — an **"Advisory only"** badge (`ui.advisory_only` is `const true`;
`em_safe.non_authoritative` is `const true`). Optional `ui.card_blurb` is a one-line subtitle.

## What it reads / what it advises (the disclosure panel)

The mod parity of a connector's `data` panel — render BEFORE the operator enables it:

| Field | Render |
|---|---|
| `advises_on` | The headline "what risk this mod surfaces" sentence. |
| `consumes` | A bulleted "reads from the evidence stream" list (e.g. `source_ref`, changed paths, excerpt text). A mod never reads a raw secret. |
| `emits` | The advisory artifact types it can produce (`routing_hint`, `source_evidence_annotation`, `advisory_governance_result`, `owner_lens_hint`, `suggested_review_question`, `dependency_signal`). |

## The trust boundary (`em_safe.forbidden_actions`) — render prominently

The mod analogue of a connector's `pii_posture` transparency surface. Render
`em_safe.forbidden_actions` as a **"This mod can NEVER:"** list (write a canonical decision, approve signoff,
resolve compliance, create a blocking CI result, bypass governance policy, mutate evidence, collapse a
confidence score). This list is validated **equal to the mod's enforced `manifest.yaml`** in CI — so what the
UI promises is exactly what the code contract guarantees. It is the operator's trust assurance: a mod suggests,
it never decides.

## Enable + configure (`enablement`)

- Render an **enable/disable toggle**; seed it from `enablement.default_enabled`.
- When `enablement.trust_gated` is true (e.g. **Noisy Source Gate**), surface that the mod's behavior depends on
  an operator-raised **source-trust** setting, and link to that control.
- Render `enablement.config[]` as typed inputs (label, default, required, description) — the optional operator
  knobs / nice-to-haves. No secrets.

## Requirements & references

Render `requirements[]` as a short "needs" note (for an EM-safe mod: the neutral evidence stream + optional
knobs — never a credential). Render `references[]` as doc links (scope spec, the mod safety contract, the ADR).

## Versioning

`mods/_schema/mod-descriptor.schema.json` `$id` versions the mod contract independently of the connector schema.
`scripts/validate_mod_config.py` keeps every mod descriptor schema-valid, **manifest-consistent** (emits +
forbidden_actions == the enforced `manifest.yaml`), and index/SETUP-fresh in CI.
