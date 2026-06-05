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

## Deferred live paths

- Live REST poll of `POST /teams/daily-usage-data` (+ members/spend) + API-key resolution + pagination.

Credentials are resolved by the operator runtime, never stored in this package.
See [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
