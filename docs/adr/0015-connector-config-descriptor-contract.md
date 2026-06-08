# ADR-0015: Connector config descriptor contract (the mcp-UI data contract)

**Date:** 2026-06-08
**Status:** Accepted
**Level:** L2 (declares credential/permission requirements consumed cross-repo)
**Relates to:** ADR-0004 (adapter boundary), ADR-0012 (operator-runtime boundary / readiness ladder)

## Context

The mcp repo must render connector configuration UI — credential entry, OAuth consent, webhook setup, a
config-on-rails wizard, permissions/PII disclosure, doc links. That knowledge lived only in prose
(`auth.md`), semi-structured tables (`references.md`), and code (`connector.py`/`runtime/poll_specs.py`/
`secrets.py`) — **not machine-consumable**.

## Decision

`bicameral-integrations` ships a **machine-readable data contract**; the mcp repo **renders** it. This
repo gains no UI code and no secret values (secrets stay in the operator runtime via `SecretResolver`).

- **`connectors/<id>/config.json`** per connector — the descriptor: identity (`id`/`name`/`description`/
  `category`/`trust_tier`/`status`/`available`/`modes`), `credentials[]` (typed: `api_key`/`oauth2`/
  `webhook_secret`/`basic`, with `scopes`/`refresh_owner`/`wiring_oversight`/`validation`/`obtain`),
  `runtime_config[]`, `webhook` (incl. **`receiver`** — the inbound URL the operator pastes INTO the
  provider, distinct from the provider's `setup.url`), `data` (`emits`/`pii_posture`), `instructions[]`
  (ordered config-on-rails, typed by `action`), `references[]`, `wire_gates[]`, `live_readiness`.
- **`connectors/_schema/connector-config.schema.json`** — the published JSON Schema (the mcp repo pins
  its `$id` version).
- **`connectors/index.json`** — a committed aggregation (one fetch for the UI), kept fresh in CI.
- **`docs/UI_RENDERING_SPEC.md`** — how each field/action renders (the contract author owns action
  semantics; the renderer is mcp's).
- **`scripts/validate_connector_config.py`** — CI enforcement (see below).

### Enforcement (`validate_connector_config.py`)

1. **Structural** — a small stdlib JSON-Schema checker driven by the schema file. **Stated limit:** it
   supports only the subset the schema uses (`type`/`properties`/`required`/`enum`/`items`/
   `additionalProperties:false`) — NOT a full JSON-Schema engine; no `if`/`then`/`oneOf`/`$ref`/`pattern`.
   It is **fail-closed**: unknown keys are rejected at every object level (the `mods/_manifest.py`
   discipline). Semantic rules JSON Schema can't cleanly express are Python post-checks (below).
2. **Semantic / code drift-guard** — `id` == folder == connector `source_id`; declared `modes` ⊆ the
   connector's `capabilities.modes` (via `importlib` of just the connector module, fail-closed
   `try/except` — connectors MUST be import-side-effect-free, ADR-0012); a `webhook` block iff a webhook
   mode; `instructions[].ref` **required** for `open_url`/`register_webhook`/`configure` (anti-fabrication
   — a provider click-path must cite its verified source).
3. **Index freshness** — committed `index.json` == a fresh aggregation.

Wired as a **standalone `ci.yml` step in this repo only**. `scripts/governance_gate.py` is deliberately
**NOT** touched: it is the portable, dependency-free gate run cross-repo against the other Bicameral
repos (which have no `connectors/` package), so importing connectors there would break it.

### The two-secret reality (surfaced, not hidden)

`SecretResolver.resolve(connector_id)` returns **one** secret per `source_id`, but some connectors need
more than one (Linear = GraphQL API key + webhook signing secret). A descriptor declares the **true**
credential needs; where the one-secret-per-id resolver can't express them, the gap is recorded in
`wire_gates[]`. Resolver key-namespacing is a **separate future runtime cycle** — the descriptive contract
ships now telling the truth.

## Consequences

- The mcp team builds config UI against a versioned, schema-valid, code-consistent contract without
  reading this repo's prose/code.
- Reference-first: Linear (api_key + webhook_secret) and Google Drive (oauth2) are the two exemplars; the
  remaining 24 connectors fan out in batched governed cycles, each validated on commit.
- OAuth is honest by construction: `oauth2` credentials mark `refresh_owner: "operator"` +
  `wiring_oversight: true` — the UI owns consent; the operator runtime owns token exchange/refresh.

## Alternatives considered

- **Structured front-matter in `references.md`** — rejected (mixes human prose + machine data; needs the
  YAML-subset parser extended for nesting).
- **Single central registry file** — rejected (loses colocation with each connector's code/tests +
  per-connector validation); the committed `index.json` aggregate serves the one-fetch UI need instead.
- **A real `jsonschema` dependency** — rejected (violates stdlib-only); the fail-closed lite checker
  suffices at this scale, with its limit stated.
- **Wiring the validator into `governance_gate.py`** — rejected (breaks cross-repo portability).
