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
- The **sole** PII control is parse-time exclusion: `parse_usage_day` reads only a non-PII aggregate
  allowlist and never reads `email` / `name` / `userId` / `clientVersion`. Do **not** relax this to
  rely on a downstream screen — there isn't one.
- **Deferred — per-developer attribution**: emitting per-user usage (joining identity to metrics)
  requires a PII redaction-and-pass model (the same gate as live Zendesk ticket bodies) and is not
  built this cycle.

## Expected secret keys (operator runtime)

- `api_key` — the team-admin Admin API key (basic-auth username) for the deferred REST poll.

## Deferred live paths

- Live REST poll of `POST /teams/daily-usage-data` (+ members/spend) + API-key resolution + pagination.
- Per-developer-attributed ingest (gated on the PII redaction-and-pass model).

Credentials are resolved by the operator runtime, never stored in this package.
See [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
