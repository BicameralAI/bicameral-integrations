# Research Brief

**Date**: 2026-06-11
**Analyst**: The Qor-logic Analyst
**Target**: Devin connector -> flip-ready parity (FX-CFG-001 descriptor + readiness ladder)
**Scope**: (1) Define the localized documentation standard a flip-ready connector must meet and enumerate Devin's gaps; (2) re-verify the Devin v3 API contract recorded in `connectors/devin/{references,auth}.md` for drift. Descriptor + docs only; NO runtime code in scope.

---

## Executive Summary

Devin is parse-surface and live-fetch complete and harness-proven (`connectors/devin/connector.py`, `runtime/poll_specs.py:build_devin_spec`, runner-wired in `runtime/runner_registry.py:81`), but it does **not** meet the localized documentation standard the two exemplars (Linear, Google Drive) meet: it lacks `config.json` (the FX-CFG-001 descriptor), the generated `SETUP.md`, membership in `connectors/index.json`, and the `live_readiness` + `wire_gates` readiness-ladder language. The v3 enterprise API contract recorded in the connector was **re-verified live today (2026-06-11)** against `docs.devinenterprise.com` and is a full **MATCH — no drift**. One new hazard is documented: a parallel **v1** Devin API (`docs.devin.ai`) has a *different* envelope/pagination/PR shape that exactly matches the drift corrected on 2026-06-08, so a future maintainer reading the wrong doc could re-introduce it.

## Findings

### Q1 — The localized documentation standard (what "flip-ready parity" requires)

Derived from `connectors/_schema/connector-config.schema.json`, the validator `scripts/validate_connector_config.py`, the two generators, and the Linear/Google_Drive exemplars. A flip-ready connector must carry:

1. **`connectors/<id>/config.json`** — schema-valid against `connector-config.schema.json` (`additionalProperties:false` at every object level; required top keys: `id, name, description, category, trust_tier, status, available, modes, credentials, data, instructions, references`). `status` enum is `scoped|candidate|beta|live-ready` (there is deliberately **no `live`** value; schema line 16).
2. **Semantic drift-guard** (`scripts/validate_connector_config.py:89-118`), all fail-closed:
   - `id` == folder name == the connector's `source_id` (`:93-100`);
   - declared `modes` subset of the connector's `capabilities.modes`, resolved by import (`:101-105`);
   - a `webhook` block **iff** `webhook` is a declared mode (`:106-108`);
   - each credential's `modes` subset of declared modes (`:109-112`);
   - `instructions[].ref` **required** for `open_url`/`register_webhook`/`configure` actions (anti-fabrication; `:113-117`).
3. **`connectors/<id>/SETUP.md`** — **GENERATED** by `scripts/build_connector_setup.py`; byte-exact freshness-checked (`validate_connector_config.py:142-147`). Hand-editing fails the gate.
4. **`connectors/index.json`** — **REGENERATED** by `scripts/build_connector_index.py`; byte-exact freshness-checked (`validate_connector_config.py:138-141`).
5. **Local provider docs** — `references.md` + `auth.md` (+ `README.md`), per the connector-doc rule.
6. **Readiness-ladder language** — `live_readiness` (string) + `wire_gates` (array) in `config.json`; optional in the schema (lines 125-126) but present in both exemplars and rendered into the SETUP.md Go-live section (`build_connector_setup.py:122-124`).

**Devin's current state vs the standard:**

| Artifact / field | Required | Devin today | Gap |
|---|---|---|---|
| `connector.py` parse surface | yes | present (`connectors/devin/connector.py`) | none |
| `references.md` (verified contract) | yes | present, doc-verified 2026-06-08 | none |
| `auth.md` | yes | present | none |
| `README.md` | yes | present | none |
| live fetch-half + runner wiring | (for active) | `build_devin_spec` (`runtime/poll_specs.py:87-98`), wired `runner_registry.py:81` | none |
| **`config.json`** (FX-CFG-001 descriptor) | **yes** | **ABSENT** | **author** |
| **`SETUP.md`** (generated) | **yes** | **ABSENT** | **generate** |
| **`index.json` membership** | **yes** | **ABSENT** (`grep -c devin` = 0) | **regenerate** |
| **`live_readiness` + `wire_gates`** | **yes** | **ABSENT** (still "Beta" in `references.md:15`) | **author into config.json** |

### Q2 — Devin v3 contract re-verification (live, 2026-06-11)

Source re-fetched today: `https://docs.devinenterprise.com/api-reference/v3/sessions/organizations-sessions`.

| Contract element | Connector record | Re-verified 2026-06-11 | Status |
|---|---|---|---|
| Endpoint | `GET /v3/organizations/{org_id}/sessions` (`auth.md`, `poll_specs.py:89` templated base_url) | `GET /v3/organizations/{org_id}/sessions` | **MATCH** |
| List envelope | `items` (`poll_specs.py:95`) | `items` | **MATCH** |
| Pagination | `end_cursor` + `has_next_page`, re-sent as `after` (`poll_specs.py:97`) | `end_cursor`, `has_next_page` (+`total`), query param `after` | **MATCH** |
| PR field | `pull_requests[]` of `{pr_url, pr_state}` (`connector.py:36-48`) | array `pull_requests` of `{pr_url, pr_state}` | **MATCH** |
| Auth | Bearer `cog_` Service-User key (`auth.md:9-13`) | Bearer, token prefix `cog_` (Service User) | **MATCH** |

`total` (integer|null) is present in the v3 response but not read by the connector — an unused optional field, **not** drift.

## Blueprint Alignment

| Blueprint Claim | Actual Finding | Status |
|---|---|---|
| `references.md`: v3 list wraps under `items`, `pull_requests[]`, cursor `end_cursor`/`has_next_page`/`after`, Bearer `cog_` | Live v3 enterprise docs confirm all five (2026-06-11) | MATCH |
| `references.md:38-39`: the 2026-06-05 `sessions`/singular-`pull_request.url`/deferred-pagination was DRIFT, corrected to v3 | The drifted shape is exactly the **v1** API (`docs.devin.ai/.../list-sessions`: `GET /v1/sessions`, `sessions`, singular `pull_request`, limit/offset, `apk_`) — a real parallel API, not the v3 surface | MATCH (correction stands; root cause = wrong-version docs) |
| Devin is "Beta" (`references.md:15`) | True today, but parse+fetch are complete and harness-proven — it is a flip-ready *candidate* once the descriptor lands | DRIFT (readiness label lags implementation) -> remediated by this cycle |

## Recommendations

1. **(P0, this cycle)** `/qor-plan` to author `connectors/devin/config.json` against the FX-CFG-001 schema: poll-only (`modes:["active"]`, no webhook block), one credential `devin` (`type:"api_key"`, `header:"Authorization: Bearer <cog_ Service-User key>"`, `modes:["active"]`), `runtime_config` entry for the required `base_url`/`org_id` templating, `data.emits:["session"]` with the redact-and-pass PII posture, `instructions` with `ref` citations to `references.md`/`auth.md`, and `live_readiness` + `wire_gates` mirroring the Linear/GDrive flip-ready posture (live REST poll operator-verified before Live; ADR-0012). **Confidence: high.**
2. **(P0)** After `config.json`, run `scripts/build_connector_index.py` + `scripts/build_connector_setup.py` (never hand-write `index.json`/`SETUP.md`), then `scripts/validate_connector_config.py` must exit 0. **Confidence: high.**
3. **(P1)** Keep runtime code untouched — the contract is verified and the fetch-half is built; this cycle is descriptor + docs only. **Confidence: high.**
4. **(advisory)** A parallel cycle should retrofit canonical hash markup to META_LEDGER entries #123+ (the `qor-logic verify-ledger` finding); out of scope here. **Confidence: medium.**

## Updated Knowledge

Recorded to `docs/SHADOW_GENOME.md`: **Devin ships TWO API versions** — v1 (`docs.devin.ai`, `GET /v1/sessions`, `sessions` envelope, singular `pull_request`, limit/offset, `apk_` keys) and v3 enterprise (`docs.devinenterprise.com`, `GET /v3/organizations/{org}/sessions`, `items`, `pull_requests[]`, cursor, `cog_` keys). The connector targets v3 by design. The 2026-06-05 drift was the v1 shape recorded against the v3 connector; reading v1 docs is the latent re-drift trap. Always cite the **enterprise** v3 doc host for this connector.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
