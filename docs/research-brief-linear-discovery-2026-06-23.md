# Research Brief — Linear resource discovery (ADR-0017 alpha provider 3/3)

**Date**: 2026-06-23
**Analyst**: The Qor-logic Analyst
**Target**: Linear discovery/fetch slice for the merged `DiscoveryConnector` surface (#178), mocked/recorded
**Scope**: Linear GraphQL discovery hierarchy (workspace→team→project→issue + comment item), auth, in-repo reuse, golden-fixture conformance, error taxonomy, the GraphQL transport seam. **No connector code written this phase.**

---

## Executive Summary

Linear is the third ADR-0017 alpha provider (after GitHub #180 and Drive #179, both merged to `dev`). Like Drive, it is **mostly recombination of existing repo code** — the GraphQL transport semantics, the no-Bearer API-key auth, the issue parse surface, and the `SecretResolver` token path are all built and verified. The net-new surface is the **discovery hierarchy queries** (teams/projects/issues/comments), which extend the repo's already-verified `_LINEAR_ISSUES_QUERY` shape. The transport seam is a **third variant** (GraphQL single-POST with query+variables, vs GitHub/Drive REST) — a local mirror, unification still deferred. No drift against ADR-0017. There is **no dedicated GH issue** for Linear discovery; this is ADR-0017 alpha-scope work grounded by the golden `linear-*` fixtures (#177).

## Findings

### F1 — Endpoint + auth — VERIFIED (repo + Linear docs)

`POST https://api.linear.app/graphql`; personal API key in the **raw `Authorization` header, NO Bearer
prefix** (`runtime/poll_specs.py:341` `ApiKeyHeaderAuth("Authorization", secret)` + host-pin
`_require_https_endpoint(..., allow=("api.linear.app",))`; Linear docs confirm `Authorization: <API_KEY>`
with no Bearer, distinct from the OAuth path). Distinct from Drive's `Bearer <token>`.

### F2 — GraphQL response/error semantics — VERIFIED (`runtime/graphql_poll.py`)

- A query can return **HTTP 200 with an `errors` array** → must **not** be treated as success
  (`graphql_poll.py:104`, `PollError "graphql_errors"`).
- **Rate-limiting is HTTP 400 + `errors[].code == "RATELIMITED"`** (not 429) — `_ratelimited` helper
  (`graphql_poll.py:69`).
- Relay pagination: `nodes` + `pageInfo { hasNextPage endCursor }`; cursor rides in the request **body**
  (`variables.after`). Verified by `_LINEAR_ISSUES_QUERY` (`poll_specs.py:305`):
  `issues(first,after,orderBy:updatedAt){ nodes{ id identifier title description url updatedAt state{name} } pageInfo{ hasNextPage endCursor } }`.

### F3 — Discovery hierarchy queries (NEW) — grounded by F2 + golden fixtures

The discovery lifecycle maps onto standard Linear schema connections (the issues shape is repo-verified; the
others extend the same `nodes`/`pageInfo` pattern; Linear docs confirm `teams { nodes { id name } }`). For the
**mocked/recorded** slice the recordings define the contract; exact field confirmation is a **live wire-gate**
(deferred, like `build_linear_graphql_spec`'s live flip):

| Resource (resource_type) | Query | Key fields → descriptor |
|---|---|---|
| workspace | `organization { id name urlKey }` | `ws_<urlKey>`, name, `https://linear.app/<urlKey>`, caps `[list,search]` |
| team | `teams(first,after){ nodes{ id key name } pageInfo }` | `team_<key↓>`, name, `…/team/<KEY>`, parent=workspace, caps `[list,read,search]` |
| project | `team(id){ projects(first,after){ nodes{ id name } pageInfo } }` | `proj_<id>`, name, `…/project/<id>`, parent=team, caps `[list,read]` |
| issue | `project(id){ issues(first,after){ nodes{ id identifier title url updatedAt priority state{name} } pageInfo } }` | `issue_<identifier>`, `<identifier>: <title>`, `…/issue/<identifier>`, parent=team, caps `[read]`, provider_metadata{priority,state} |

Matches golden `linear-workspace`/`linear-team`/`linear-project`/`linear-issue-comment-path.json` (id prefixes
`ws_`/`team_`/`proj_`/`issue_`).

### F4 — Item fetch (issue + comment) — reuse `parse_issue_node` content

- **issue item**: `issue(id){ identifier title description url updatedAt state{name} team{key} }` → reuse the
  excerpt logic of `connectors.linear.connector.parse_issue_node` (`connector.py:91`; PII-safe — no
  assignee/creator identity) for the `ProviderItemEnvelope.content`. Matches golden `items/linear-issue.json`.
- **comment item**: `issue(id){ comments(first,after){ nodes{ id body createdAt } pageInfo } }` → `comment_<id>`,
  content = `body`. Matches golden `items/linear-comment.json` (`provider_metadata.parent_issue_identifier`).

### F5 — In-repo reuse map

| Need | Existing asset | File:line |
|---|---|---|
| API key (operator-side), raw Authorization | `SecretResolver` + `ApiKeyHeaderAuth("Authorization", key)` | `runtime/secrets.py:15`, `runtime/poll_auth.py:45` |
| GraphQL POST + 200-errors / 400-RATELIMITED semantics | `graphql_poll._decode` / `_ratelimited` | `runtime/graphql_poll.py:69,90` |
| Issue node parse (content + PII-safety) | `parse_issue_node` | `connectors/linear/connector.py:91` |
| Descriptor/item screen (fail-closed) | `screening.py` (`screen_descriptor`/`screen_item`) | `protocol/provider_acquisition/screening.py` (on dev) |
| Recorded-fixture + taxonomy pattern | #180/#179 connectors | `protocol/provider_acquisition/{github,google_drive}/` (on dev) |

### F6 — Error/permission taxonomy → merged `DiscoveryErrorKind` (5 values)

| Linear signal | Kind | permission_state |
|---|---|---|
| token provider returns `""` (no API key) | `ACTION_NEEDED` | `action_needed` |
| 200-with-`errors` auth (`AUTHENTICATION_ERROR` / invalid key) | `ACTION_NEEDED` | `action_needed` |
| 200-with-`errors` forbidden (`FORBIDDEN` / no access) | `PERMISSION_DENIED` | `denied` |
| 200-with-`errors` not-found (`ENTITY_NOT_FOUND`) | `NOT_FOUND` | — |
| unsupported resource/item kind (bad id prefix) | `UNSUPPORTED` | — |
| HTTP 400 + `RATELIMITED` / other transport error | `PROVIDER_ERROR` | — |

### F7 — Transport seam (GraphQL, third variant)

GitHub/Drive are REST (path-routed); Linear is a **single POST endpoint with a `{query, variables}` body**. So
the local seam is `execute(operation, query, variables) -> LinearResponse(status, data, errors)`; the
`RecordedTransport` routes on **operation name + variables** (stable, readable — no raw query string in keys).
The live `urllib` POST is deferred (a mock never promotes to Live — ADR-0012). **Token provider = the existing
`SecretResolver`** (reuse, no new type). Local mirror — **do not touch #178/#179/#180 code**; unification of the
three transport seams stays deferred (each is provider-shaped: REST-path, REST-path+params, GraphQL-POST).

## Blueprint Alignment

| ADR-0017 / fixture claim | Finding | Status |
|---|---|---|
| Linear alpha: team→project→issue (+comment item); workspace = account_label | F3/F4 hierarchy + golden fixtures | MATCH |
| Discovery returns descriptors/items, never authority; `create_provider_resource` absent | read-only; no writes | MATCH |
| Reuse one `adapter.core.sensitive` screen | `screening.py` reused | MATCH |
| Mocked earns Beta; Live needs operator creds + real call | live GraphQL POST deferred | MATCH |
| Linear API key raw Authorization (no Bearer) | F1 (repo + docs) | MATCH |

## Recommendations (for /qor-plan)

1. `list_resources` dispatches on `config`: none→teams (under the workspace), `team_id`→projects, `project_id`→issues. `get_resource` by id prefix (`ws_`/`team_`/`proj_`/`issue_`). `fetch_provider_item`: `issue_*`→issue item (reuse `parse_issue_node` excerpt), `comment_*`→comment item.
2. **Reuse `SecretResolver`** (raw Authorization, no Bearer) + `screening.py`; local GraphQL transport mirror.
3. Recorded fixtures under `fixtures/recorded/linear/` (operation+variables routed) incl. a **200-with-errors auth** case and a **400 RATELIMITED** case — secret-guard `rglob`-covered; no token material.
4. Razor: factor `auth.py`/`errors.py`/`transport.py`/`queries.py`/`mapping.py` to keep `connector.py` < 250 (as #179).
5. ADR-0017 Addendum for Linear; **no `connectors/linear/config.json` change** (discovery block deferred to the ADR-0015 fan-out).
6. Id-splice guards where identifiers/ids enter a query variable (defense-in-depth, mirroring the #179 doc-id guard).

## Open Questions / risks

- **OQ1 (live wire-gate)**: exact field names for `organization.urlKey` / `team.key` / `project` / `comment.body` are standard Linear schema but confirmed live only at the flip (deferred; the recordings define the mocked contract). Non-severe.
- **OQ2 (no tracked issue)**: Linear discovery has no GH issue (unlike #179/#180). This cycle is ADR-0017 alpha-scope. A tracking issue could be opened by the operator if desired.
- **OQ3 (ledger)**: this branch is off `dev` head #219; research entry is **#220** (clean continuation — no fork, since #179/#180 already merged).

## Updated Knowledge

SG-2026-06-23-A extended: the discovery **token provider is provider-agnostic** (`SecretResolver` for Drive + Linear; only GitHub needed a new installation-token type) and **screening is shared**; the **transport seam is provider-shaped** (REST-path / REST-path+params / GraphQL-POST) — three local mirrors, unification deferred until a fourth provider proves the common shape.

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor (/qor-plan next)._
