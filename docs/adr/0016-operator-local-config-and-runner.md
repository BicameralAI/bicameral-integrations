# ADR-0016: Operator-local config + headless runner

**Date:** 2026-06-08
**Status:** Accepted
**Level:** L2 (reads real secrets; can egress to the gateway)
**Relates to:** ADR-0012 (operator-runtime boundary), FX-CFG-001 (the config descriptor contract)

## Context

Connectors + mods were library-only: running one needed hand-written Python to wire a `SecretResolver`
+ spec + transport + sink. The mcp UI would do that wiring — making the UI an implicit blocker for using
the connectors/mods at all. Operators (and CI/cron/scripts) need a **headless** way to configure + run
them now, without the UI, and permanently after.

## Decision

A **file/env-backed config + a runner CLI** (`python -m runtime.cli`). The just-shipped
`connectors/<id>/config.json` descriptors declare *what* each connector needs; the local config supplies
the *values*; the loader cross-checks the two.

- **`runtime/local_config.py`** — `FileSecretResolver` (env `BICAMERAL_<KEY>` wins **only when set and
  non-empty**, else the flat file map, else `""`); `load_config` (fail-closed; rejects non-dict/unknown
  keys; **rejects a duplicate credential key** across connectors; `_`-prefixed keys are comments);
  `assert_runnable` (hard-fail, token-free, KEY-NAME-only, on an unknown or missing-required credential
  for the *target* — required creds checked via the resolver so an env-only operator passes);
  `validate_against_descriptors` (advisory cross-check for `list`).
- **`runtime/runner_registry.py`** — `RUNNERS` maps a connector id to a uniform runner, absorbing the
  call-shape asymmetry (`poll` takes a `PollConnector` first-arg; `poll_graphql`/`fetch_document` do not).
  Wires `linear` (GraphQL), `google_drive` (documents.get), and the 7 REST poll connectors. `load_mod`
  pins the manifest path, fail-closed.
- **`runtime/cli.py`** — `list` / `run <connector>` / `run-mods <connector>`. Default sink is local
  `CollectingSink` (prints **screened** emissions: `source_id`/`title`/`excerpt` — never a secret);
  `--sink gateway` does a real POST (default-gated, `GatewayEmissionGated` if unconfigured). `--limit`
  caps printed emissions. The testable core (`run_connector`/`run_mods`) takes an injected transport+sink
  so tests drive a `RecordedTransport`; only `main()` uses `UrllibTransport`.

### Security posture

- **Never commit secrets.** Secrets live in a **gitignored** `config/bicameral.local.json` (glob block
  `config/bicameral.local*.json` + `config/*.local.json` + `config/secrets*.json`, with the example kept
  via `!config/bicameral.example.json`) or in env. Two backstops: a test asserts the glob ignores the
  canonical name + variants; a test scans every **tracked** `config/*.json` for real secret SHAPES
  (`lin_api_`/`ya29.`/`AKIA`/`whsec_`/JWT/`Bearer <token>`) — independent of TruffleHog's `--only-verified`.
- **No secret reaches stdout/stderr/log/exception.** `FileSecretResolver` never echoes a value; the CLI
  prints only screened emissions; `main()`'s except handler prints `str(exc)` only (never `repr` the
  `LocalConfig`/`gateway`, which holds the token); every `ConfigError`/`PollError` names KEYS, not values.
- **Plaintext-secret-on-disk** in a gitignored operator file is the **accepted posture** (operator owns
  the file permissions + must not sync it); **env-override is the no-disk escape hatch**.
- `--sink gateway` (real egress) is **default-gated** and an explicit opt-in (Review Boundary); FX-SEC-001
  screens every emission before any sink.

## Consequences

- An operator can `run` any wired ACTIVE connector and `run-mods` a mod **headless, no UI**, from one
  gitignored file (or env). The CLI-in-`runtime/` is a **run-once entrypoint, not a daemon** — it does not
  make the library a server.
- Reference-first: `linear` + `google_drive` + `dependency_risk` are the proven exemplars; the registry is
  the extension point for the connector/mod fan-out.

## Amendment 2026-06-08 — multi-secret + mode-scoped credentials (FX-RUNTIME-005)

Resolves the `linear_webhook` over-require residual below. **Credential-key namespacing is formalized:**
a connector resolves each secret by its credential **key** (`SecretResolver.resolve(key)`) — single-secret
connectors use their `source_id`; multi-credential connectors use namespaced keys `<connector>[_<purpose>]`
(`linear` + `linear_webhook`), globally unique by the `load_config` dup-key guard, env `BICAMERAL_<KEY>`.
**`assert_runnable(config, id, *, mode="active")` is now mode-scoped:** a credential declares
`config.json` `credentials[].modes`; the runner requires only credentials serving the run's mode, where an
**absent OR empty `modes` means all-mode** (`mode in (c.get("modes") or [mode])`). So an active
`run linear` requires only `linear`; `linear_webhook` (`modes:["webhook"]`) is not demanded. The unknown-key
rejection stays mode-independent (a typo'd key hard-fails on any mode), and a genuinely-missing active
credential still fail-closes at `_require_secret`. **Residual:** injecting the webhook signing secret into
`deliver_webhook`'s *receive* path stays operator-runtime (the CLI runs active fetches, not webhook receipt).

## Residual / accepted limitations

- ~~**`linear_webhook` over-require**~~ — **resolved** by the FX-RUNTIME-005 amendment above (mode-scoped
  `assert_runnable`). The webhook-*receive* secret injection into `deliver_webhook` remains operator-runtime.
- **`--only-verified`** in the secret scanner won't flag a pasted-but-revoked/non-verifiable key, and the
  shape-scan can't catch a **prefix-less** secret (e.g. a ServiceNow Basic password) — for those the
  **gitignore glob is the primary control**. Accepted residual.

## Alternatives considered

- **Env-only secrets** — rejected as the default (the operator asked for a file); env remains the override.
- **CLI in `scripts/`** — `runtime/` is the operator-runtime boundary (ADR-0012); the runner belongs there.
