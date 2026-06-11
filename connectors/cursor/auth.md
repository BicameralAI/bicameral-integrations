# Cursor Auth

Auth model recorded for the live cycle; this connector ships the **parse surface** only
(live REST poll deferred).

- Default trust tier: T1 (read) / ACTIVE (poll).
- **No webhook**: Cursor publishes no webhooks for usage data — ingestion is an outbound REST
  poll, so there is no signed inbound surface and no `verify()`.
- **Active fetch auth (deferred)**: the Cursor Admin API uses **HTTP Basic with the API key as
  the username and an empty password** (`-u YOUR_API_KEY:`). Only team administrators can mint
  keys; key custody is admin-only. The key is resolved by the operator runtime, never stored here.
- **Endpoints (deferred poll)**: `POST /teams/daily-usage-data` (date range; poll ≤ hourly),
  `GET /teams/members`, `POST /teams/spend`.

## Privacy / PII (binding design contract)

- The `daily-usage-data` rows are **PII-dense**: every row carries `email`; `name` appears in the
  members/spend endpoints. **FX-SEC-001 screens secret/PHI/PAN only — it does NOT detect a generic
  email**, and never scans `Observation.metadata` ([SG-2026-06-05-A](../../docs/SHADOW_GENOME.md)).
- The PII control is parse-time exclusion: `parse_usage_day` reads only a non-PII allowlist and
  **never reads `email` / `name` / `clientVersion`**. Do **not** relax this to rely on a downstream
  screen — there isn't one (FX-SEC-001 doesn't detect generic email).
- **Per-developer attribution (IMPLEMENTED — SG-2026-06-05-D supersedes -A for `userId` only)**: the
  **opaque integer `userId`** is now surfaced (in `ref` + excerpt) as the attribution key. A bare vendor
  id is pseudonymous on its own; `email`/`name` are still never read, so identity is never emitted.
  **Residual risk (accepted):** an operator holding the vendor id→identity mapping can re-identify —
  acceptable for an operator-run evidence adapter.

## Expected secret keys (operator runtime)

- `api_key` — the team-admin Admin API key (basic-auth username) for the deferred REST poll.

## Live path — reference poll client (contract verified 2026-06-08, RE-VERIFIED LIVE 2026-06-11, cursor.com/docs/account/teams/admin-api)

The request-construction is **built** in `runtime/poll_specs.py` (`build_cursor_spec`) and proven
against a recorded fixture. The real network call + key resolution remain operator-run.

- **Secret resolver key**: the `SecretResolver` resolves by the connector **`source_id`** (`cursor`);
  the `api_key` name below is the credential's *meaning* (it is sent as the basic-auth username).
- **Verified**: host `api.cursor.com`; `POST /teams/daily-usage-data` with HTTP **Basic** (key as
  username, empty password); body `{startDate, endDate}` in **epoch milliseconds**, range ≤ 30 days
  (caller supplies the dict — still not baked); response **`data`** envelope. Each row carries
  `email` + opaque `userId` (the connector reads neither identity beyond the opaque `userId`; there
  is **no `name`** field on this endpoint — earlier docs overstated it).
- **Pagination — VERIFIED 2026-06-11 (transport resolved): POST-body based.** `page` (1-indexed) and
  `pageSize` ride in the **POST body** alongside `startDate`/`endDate`; the response carries a
  `pagination` object (`page`, `pageSize`, `totalUsers`, `totalPages`, **`hasNextPage`**, `hasPreviousPage`).
  The earlier "query-vs-body unclear" note is RESOLVED — it is **body**. The reference pager is still
  **NOT wired** (`build_cursor_spec` issues a single request), so a team larger than one page truncates;
  the build cycle either wires a body-page pager (read `pagination.hasNextPage`, send `page`/`pageSize`
  in the body) or the operator widens `pageSize`. Note `runtime/poll_specs.py` (build_cursor_spec) still
  carries STALE "host inferred / body+envelope unverified" comments — reconcile them to this verified
  contract in the build cycle.

## Deferred live paths

- Live REST poll of `POST /teams/daily-usage-data` (+ members/spend) + API-key resolution (the
  `runtime/` poll client is built; the operator supplies the live transport + secret + body-shape
  confirmation).

Credentials are resolved by the operator runtime, never stored in this package.
See [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
