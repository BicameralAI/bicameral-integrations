# Connector Config — UI Rendering Spec (for the mcp repo)

**Status:** Reference spec (v1, 2026-06-08). **This is a contract for the mcp UI team, not code.**

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

## Permissions / data disclosure (`data`)

Show `data.emits`, `data.pii_posture`, OAuth `scopes`, and `trust_tier` as a "what this connector can see
/ emit" panel before the operator connects — the transparency surface.

## References & gates

Render `references[]` as doc links; render `wire_gates[]` + `live_readiness` as a pre-go-live checklist
the operator must clear (these are the "not yet confirmed against live" items).

## Versioning

The schema's `$id` versions the contract. Breaking field changes bump it; the mcp repo pins a schema
version. The validator (`scripts/validate_connector_config.py`) keeps every descriptor + the index in
sync in CI, so what the UI imports is always schema-valid and code-consistent.
