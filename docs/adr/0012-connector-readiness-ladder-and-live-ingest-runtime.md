# ADR-0012: Connector readiness ladder + live-ingest runtime boundary

**Status**: Accepted (2026-06-04)
**Context cycle**: `go-live-runtime-2026-06-04`

## Context

17 connectors are implemented but all sit at one flat readiness — "Prototype" —
because the project deliberately deferred the *live boundary*: every connector
is an injectable parse(+verify) **library** surface tested against fixtures, and
each `auth.md` states "the operator runtime injects the secret + dedup cache."
Nothing actually receives a webhook, polls an API, resolves a secret, or emits
to the gateway. The operator (rightly) flagged this as breadth-over-depth and
asked to take flagship connectors "live."

Two facts constrain the design:
- **Runtime stays stdlib-only** (no third-party runtime deps; see SYSTEM_STATE
  Dependency Manifest). A heavyweight web framework is out.
- **Gateway emission is not safely available yet**: the v1 ingest wire schema is
  published (bicameral-bot PR #95, `protocol/schemas/v1/`), but the gateway
  `POST /api/v1/ingest` lacks ingest guards (bot **#109**, open, assigned), and
  the ingest authority is mid-refactor (MCP→ToolRequest, bot #114/#115/#120).
  (The earlier "blocked on bot #99" claim was a misattribution — SG-2026-06-04-N.)

## Decision

### 1. Readiness ladder (replaces the flat "Prototype")

| Stage | Meaning | Gate to enter |
|---|---|---|
| **Candidate** | catalogued; no `connector.py` | — |
| **Prototype** | parse surface (+ `verify()` where the provider signs) implemented, tested against synthetic fixtures; no live boundary | parse + tests green |
| **Beta** | wired into the runtime harness — a tested `ingest → verify → normalize → emit(sink)` path with injected secret + dedup + a reference sink; still no production gateway emission | runtime harness test green end-to-end |
| **Live** | emitting to the deployed bicameral-bot gateway (`/api/v1/ingest`, v1 schema) from an operator runtime | **bot #109** (gateway ingest guards) + a pinned v1 mapping + operator deployment |

### 2. The repo stays a library; a thin `runtime/` layer is the boundary adapter

This repo does **not** become a web server (preserves stdlib-only + the
ADR-0006 / `auth.md` "operator runtime owns the live HTTP boundary" convention).
"Going live" adds a thin, framework-free `runtime/` layer the operator's host
(or the bot daemon) calls:

- **`EmissionSink` protocol** — `emit(emissions: list[AdapterEmission]) -> None`.
  Reference impls: `CollectingSink` (in-memory, for tests) + a `GatewaySink`
  **stub** (see 3).
- **`SecretResolver` protocol** — `resolve(connector_id: str) -> str`. The
  operator runtime provides real keyring resolution; a reference
  `MappingSecretResolver` (dict/env) serves Beta + tests. Secrets are never
  stored in this package.
- **delivery orchestration** — `deliver_webhook(connector, *, headers, body, sink)`
  (calls the connector's `normalize_event` then `normalize` → `sink.emit`) and
  `deliver_poll(connector, payloads, sink)` for ACTIVE connectors. The actual
  HTTP server / cron stays in the operator runtime, which calls these.

### 3. Gateway emission is a #109-gated stub

`GatewaySink` documents the production target (map `AdapterEmission` → the v1
ingest payload, `POST /api/v1/ingest`) but **does not emit**: its `emit` raises
`GatewayEmissionGated` with the reason (bot #109 ingest guards pending; the exact
`protocol/schemas/v1/` field mapping to be pinned when #109 lands). This makes
the emission *contract* explicit and testable (the gate is asserted, not
silently skipped) without fabricating an unverified wire mapping or pushing
traffic at an unhardened endpoint. Promoting a connector to **Live** = wiring a
real `GatewaySink` once #109 is done.

## Consequences

- A connector reaches **Beta** with zero cross-repo dependency (everything is
  ours: harness + reference sink + secret resolver + dedup). **Live** is the only
  stage gated on the bot (#109 + pinned v1 mapping).
- The connector index gains a real readiness signal (Prototype / Beta / Live)
  instead of a flat "Prototype."
- No production webhook server lives here; operators wire the `runtime/` layer
  into their own receiver/cron. This keeps the trust boundary where ADR-0006 /
  ADR-0008 put it.
- First connector promoted to Beta: **Linear** (already verify-wired; webhook).

## Alternatives considered

- **Become a web server (FastAPI/Flask)** — rejected: breaks stdlib-only, moves
  the live HTTP boundary into the library against ADR-0006, and couples deploy.
- **Wait for bot #109 before any go-live work** — rejected: Beta (the bulk of the
  value — real ingest→verify→normalize→emit) needs nothing from the bot; only
  production gateway emission does.
- **Emit to the gateway now with a best-guess v1 mapping** — rejected: would
  fabricate an unverified wire schema and push at an unhardened endpoint (#109).
