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
| **Live** | emitting to the deployed bicameral-bot gateway (`/api/v1/external-ingest`, v2 `ExternalIngestEnvelope` — amended 2026-07-08, #226) from an operator runtime | a pinned v2 mapping + operator deployment (bot #109 guards landed; external-ingest handler adds authority-stripping) |

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

### 3. Gateway emission — implemented (bot #109 landed 2026-06-05; retargeted to external-ingest 2026-07-08, #226)

`GatewaySink` is the real **Live** seam. It maps each `AdapterEmission` to the
v2 `ExternalIngestEnvelope` (the mapping is pinned in `runtime/gateway_mapping.py`
against a vendored copy of `bicameral-bot:protocol/schemas/v2/external-ingest-request.schema.json`,
schema commit `5c24c60f`) and `POST`s it to a configured `/api/v1/external-ingest`
with stdlib `urllib` — the **authority-stripped external path** ("Integrations
acquire. Bot materializes. MCP routes."; the legacy `/api/v1/ingest` is the
local/MCP-actor contract and is no longer used from this repo). The gateway 403s
18 forbidden authority fields; the envelope is authority-free by construction and
regression-locked. It is:
- **default-safe** — with no endpoint, `emit` still raises `GatewayEmissionGated`
  (the operator opts in by configuring `GatewaySink(endpoint=…)`);
- **fail-closed** — `emit` re-runs the producer contract + secret/PII/PAN screen
  at the emission boundary (so a hand-built emission cannot bypass it), accepts
  only HTTP **201**, and raises `GatewayEmissionError(status, reason)` on any
  other status or transport fault (the operator handles rejections/retries);
- **secret-safe** — the auth token is operator-injected (`token` →
  `Authorization: Bearer`) and never appears in an error or log.

Bot **#109** (gateway ingest guards: body-size / rate / sensitive-data) merged
(PR #131), so the endpoint is hardened. Dimensional confidence is deliberately
not collapsed into a wire scalar (SG-2026-06-02-B); the envelope's advisory
`candidate_hints` carry the title/body signal only — the daemon classifies
`level` itself (bot ADR-0024). Promoting a
connector to **Live** = an operator wiring a configured `GatewaySink` against a
real gateway — the repo delivers the verified seam; the operator deployment is
what earns Live (a mock test does not promote a connector to Live).

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
