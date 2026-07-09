# Research Brief

**Date**: 2026-07-08
**Analyst**: The Qor-logic Analyst
**Target**: GH #227 — `runtime.cli configure <connector>` config-on-rails (CLI go-live path for mcp#572); acceptance targets Linear + Google Drive
**Scope**: (1) runtime surfaces the `configure` subcommand builds on; (2) descriptor contract the walk is driven by; (3) production-readiness state of Linear + Google Drive (operator ask: "priority integrations fully production ready"); (4) drift between #227's stated assumptions and code reality

---

## Executive Summary

The descriptor contract, config store, secret resolver, and per-connector run harness all exist and are
harness-proven — #227 is a **thin guided layer over verified primitives**, not new machinery. Three drifts
matter for planning: the local config store is **read-only today** (no writer exists anywhere), the OAuth
module has **no auth-code→refresh-token exchange** (only refresh→access), and `resolver_from` **never wires
`RefreshTokenSecretResolver`** into the run path — so `configure google_drive`'s `verify` step cannot pass
on a persisted refresh token without also extending the resolver wiring. Linear + Google Drive are
**flip-ready, NOT Live** (ADR-0012): code + tests + runbooks complete; every remaining gap is exactly the
operator credential/config/live-test step that #227 automates. #227 **is** the production-readiness path.

## Findings

### F1 — CLI structure: clean slot-in point

- `runtime/cli.py:116` `_parser()` — argparse, `prog="runtime.cli"`, global `--config` (default
  `config/bicameral.local.json`), required subparsers `list` / `run` / `run-mods` (cli.py:120-128).
- `runtime/cli.py:132` `main(argv) -> int` dispatches on `args.command`; catches `ConfigError`, `PollError`,
  `GatewayEmissionGated`, `FileNotFoundError` with token-free messages (cli.py:132-143).
- A `configure` subcommand slots in as a fourth subparser + `_cmd_configure(config_path, args)` branch.
  Note: `main` calls `load_config(args.config)` *before* dispatch — `configure` must tolerate a **missing**
  config file (it creates one), so the dispatch order needs a small refactor or an early branch before
  `load_config`.

### F2 — Local config store is READ-ONLY today (write path is net-new)

- `runtime/local_config.py` (ADR-0016, FX-RUNTIME-004): `load_config(path)` (local_config.py:55-80) parses +
  fail-closed-validates; `LocalConfig` is a **frozen** dataclass (local_config.py:31-38). **No function in
  the repo writes `config/bicameral.local.json`.**
- Shape (validated): top-level `connectors` / `mods` / `gateway`; connector block keys exactly
  `enabled|secrets|runtime` (frozen sets local_config.py:23-24); `_`-prefixed keys are comments;
  **credential keys are globally unique** — duplicate across connectors → `ConfigError`
  (local_config.py:76-79).
- Runtime-key allowlist: a `runtime` sub-key not declared in the descriptor's `runtime_config` is rejected
  (local_config.py:126-132) — `configure` must only write declared keys.
- `config/bicameral.example.json` is the seed shape (linear, google_drive, anthropic_admin entries,
  all `enabled:false`).

### F3 — Secret resolution + key namespacing (FX-RUNTIME-005)

- `SecretResolver` protocol: single method `resolve(key: str) -> str`, empty string on miss
  (`runtime/secrets.py:14-24`).
- `FileSecretResolver.resolve`: env `BICAMERAL_<KEY>` (upper-cased key) wins **if set and non-empty**, else
  flat file map (local_config.py:41-52). ⚠ Consequence for `configure`: a stale env var **silently masks**
  a freshly-written file value — the command should detect and warn (key name only, never value).
- `assert_runnable(config, id, *, mode)` (local_config.py:106-139) is the existing mode-scoped credential
  gate: requires only credentials whose `modes` include the requested mode (absent/empty = all modes) —
  reuse it; do not reimplement.
- `resolver_from(config)` returns plain `FileSecretResolver(config.secret_map)` (local_config.py:83-84).

### F4 — OAuth: no auth-code exchange exists (loopback flow is net-new)

- `runtime/google_oauth.py` (FX-RUNTIME-006): `RefreshTokenSecretResolver(target_key, refresh_token,
  client_id, client_secret, transport, base, clock)` (google_oauth.py:43-70) mints access tokens via plain
  form POST to `https://oauth2.googleapis.com/token` (google_oauth.py:81-87); in-memory cache w/ 60s skew;
  token-free `OAuthRefreshError(status, reason)` (google_oauth.py:33-40); 1 MiB body cap; stdlib-only
  (no RSA — research #125 F2; service-account RS256 explicitly out of repo scope, google_oauth.py:6-7).
- **There is no `authorization_code` grant helper** and no loopback redirect catcher anywhere in the repo.
  #227's `oauth_consent` (browser + `http.server` on `127.0.0.1:<ephemeral>` + code→refresh-token exchange
  incl. PKCE) is entirely new code.

### F5 — DRIFT: refresh resolver is not wired into the run path

- `RefreshTokenSecretResolver` is constructed **only in tests** (`runtime/tests/test_google_oauth.py:47-48`);
  `run_connector` (cli.py:33-52) passes `resolver_from(config)` — a bare `FileSecretResolver`.
- Today, `run google_drive` therefore requires a raw ~1h access token under secret key `google_drive`.
  If `configure` persists a refresh-token triple, the `verify` action (which calls `run_connector`) will
  send the **refresh token as the Bearer token** and fail. → The plan must extend resolver construction
  (e.g. wrap `FileSecretResolver` with `RefreshTokenSecretResolver` when the google_drive refresh-token
  keys are present) **and** decide the persisted key shape (candidates: `google_drive_refresh_token`,
  `google_drive_client_id`, `google_drive_client_secret` — flat, globally-unique keys; note
  `validate_against_descriptors` will emit advisory unknown-key warnings unless taught otherwise,
  local_config.py:92-103).

### F6 — Descriptor contract: verified against schema + both target descriptors

- Schema `connectors/_schema/connector-config.schema.json`: `instructions[].action` enum is **exactly the
  six** claimed (schema line 111): `open_url|paste_secret|oauth_consent|register_webhook|configure|verify`.
  `credentials[]` carries `key/type/label/required/modes/scopes/refresh_owner/validation/header/obtain`
  (lines 21-48); `runtime_config[]` carries `key/label/required/default/description` (lines 50-62);
  `available` (line 19) is the canonical availability flag (UI_RENDERING_SPEC.md:36 concurs).
- **Linear** (`connectors/linear/config.json`): 5 instructions (open_url → paste_secret → register_webhook
  → paste_secret → verify). Credentials: `linear` (api_key, modes `["active"]`, validation
  `^lin_api_[A-Za-z0-9]+$`, **raw** `Authorization` header, no Bearer) + `linear_webhook` (webhook_secret,
  modes `["webhook"]`). `runtime_config`: `page_size` (optional, default 50).
- **Google Drive** (`connectors/google_drive/config.json`): 3 instructions (oauth_consent → configure →
  verify). One credential `google_drive` (oauth2, modes `["active"]`, scopes documents.readonly +
  drive.readonly, `refresh_owner:"operator"`, `wiring_oversight:true`). `runtime_config`: `document_id`
  (required; runtime validates `[A-Za-z0-9_-]{1,200}` at `runtime/poll_specs.py:338,345`).
- `docs/UI_RENDERING_SPEC.md:54-64` gives per-action semantics the CLI mirrors in text mode.
- Loaders to reuse: `_descriptor(connector_id)` (local_config.py:87-89) reads
  `connectors/<id>/config.json`; CI validator `scripts/validate_connector_config.py` guarantees every
  descriptor is schema-valid (fail-closed), so the CLI may trust descriptor shape.

### F7 — No interactive surface exists today

Zero `getpass`/`input()` in `runtime/` — the runner is deliberately headless. `configure` is the repo's
first interactive command; keep the interactivity inside `_cmd_configure` handlers so the rest of the
runtime stays non-interactive, and design prompts as injectable (function params) for testability.

### F8 — `verify` action harness exists

`run_connector(connector_id, config, transport, sink, *, document_id, limit)` (cli.py:33-52) →
`RUNNERS` registry (`runtime/runner_registry.py:95-106`) → `assert_runnable(..., mode="active")` →
runner with resolver/runtime/transport/sink. Live transport = `UrllibTransport`; tests use
`_RecordingTransport` fixtures (`runtime/tests/test_cli.py:26-36`). `verify` = run against
`CollectingSink` + report count; recorded-transport injection makes the acceptance test tractable.

### F9 — Conventions the implementation must match

Python 3.13 (ci.yml:20); stdlib-only runtime (cli.py:7 docstring); pytest style w/ `monkeypatch`/
`tmp_path`/`capsys`; CI = `ruff check adapter connectors runtime mods` + whole-tree `mypy` (SG-2026-06-12-D)
+ `pytest adapter/core/tests connectors runtime mods scripts/tests tests/redteam -q` + both descriptor
validators. Token-free error discipline throughout (no secret in message, `from None` to sever cause
chains — google_oauth.py:94-95 pattern).

### F10 — Production-readiness state: Linear + Google Drive (operator goal)

Both are **flip-ready, NOT yet Live** (ADR-0012: a mock does not promote to Live). Code, tests
(webhook verify `connectors/linear/connector.py:153-164`; GraphQL poll `runtime/graphql_poll.py:124-163`;
documents.get `runtime/doc_fetch.py:58-76`; OAuth refresh google_oauth.py:43-109; GatewaySink
`runtime/sinks.py:99-150`), purple-team approval (ledger #133), and operator runbooks
(`docs/runbooks/golive-linear.md`, `docs/runbooks/golive-google_drive.md`) are complete.
**Every remaining gap is operator-side**: credential placement, webhook registration (Linear),
durable-credential choice + document id (Google Drive), gateway endpoint wiring, live 201 test.
Discovery slices (ADR-0017) are fixture-only Alpha by design — not go-live blockers.
**#227 is precisely the tool that closes the credential/config portion of these gaps**; the live 201
test remains a human-reviewed operator action (ADR-0012), out of #227 scope.

## Blueprint Alignment

| #227 Claim | Actual Finding | Status |
|---|---|---|
| "`runtime/local_config.py` … the config **store** exists" | Store exists but is read-only; no writer anywhere | **DRIFT** (writer is net-new — in scope, plan it explicitly) |
| "exchange for a refresh token … durable path via `RefreshTokenSecretResolver`" | No auth-code grant helper exists; resolver only does refresh→access; resolver never wired into run path | **DRIFT** (loopback+exchange net-new; resolver wiring must be added or `verify` fails) |
| "six types in `connector-config.schema.json`" | Exactly six, enum verified (schema line 111) | MATCH |
| "validate against `credentials[].validation` regex" | Linear: `^lin_api_[A-Za-z0-9]+$`; Google Drive credential has **no** validation regex (only runtime `document_id` pattern) | MATCH (handle absent regex = accept) |
| "Mode-scoped (FX-RUNTIME-005) … drive credential set from `credentials[].modes`" | Schema + `assert_runnable` implement exactly this (local_config.py:134-136) | MATCH (reuse, don't rebuild) |
| "Create `config/bicameral.local.json` from `config/bicameral.example.json` if absent" | Example exists, matches validated shape | MATCH |
| "`run_connector(...)` against the recorded-transport/live harness" | cli.py:33-52 + injectable `HttpTransport` | MATCH |
| "Stdlib-only (matches repo ethos)" | Confirmed (no pyproject/requirements; docstrings declare stdlib-only) | MATCH |
| "Linear + Google Drive are the two acceptance targets" | Both descriptors verified; both flip-ready | MATCH |

## Recommendations

1. **(P0)** Plan `configure` as: descriptor-driven instruction walk (six action handlers) + **new atomic
   config writer** (`local_config.py` or sibling module; write-temp-then-replace; never log values) +
   `--config` path respected; create-from-example when absent; set `enabled:true` on success.
2. **(P0)** Include **resolver wiring** in scope: `resolver_from`/run-path upgrade so a persisted
   google_drive refresh triple mints access tokens via `RefreshTokenSecretResolver`; define the three
   flat secret keys; suppress/teach the advisory descriptor cross-check for them.
3. **(P0)** `oauth_consent`: new stdlib loopback helper (auth URL w/ scopes + PKCE, `http.server` catcher
   on 127.0.0.1 ephemeral port, code→refresh-token exchange POST); `--paste-token` escape hatch with
   explicit ~1h non-durable warning (copy per descriptor wire_gates).
4. **(P1)** `main()` dispatch: branch `configure` **before** `load_config` (file may not exist yet).
5. **(P1)** Warn (key name only) when `BICAMERAL_<KEY>` env masks a value just written to file (F3).
6. **(P1)** Prompt seams injectable for tests: masked input via `getpass` only at the CLI edge;
   handlers take `input_fn`/`getpass_fn`/`transport` params.
7. **(P2)** After #227 lands, the residual go-live work for Linear + Google Drive is the operator live
   201 test per runbooks — track as operator action, not code.

## Updated Knowledge

- `resolver_from` returns a bare `FileSecretResolver`; `RefreshTokenSecretResolver` has never been wired
  into the CLI run path (tests only) — recorded here to prevent plan-time assumption drift.
- `qor-logic verify-ledger` / `governance-health` per-entry "canonical hash markup" FAILs on #123+ are a
  **known cross-tool mismatch** (ledger tail note; repo `scripts/governance_gate.py` re-derives #1..#228
  clean) — non-gating, standing /qor-remediate candidate. No new SHADOW_GENOME entry warranted (no failed
  approach; facts recorded in this brief).

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
