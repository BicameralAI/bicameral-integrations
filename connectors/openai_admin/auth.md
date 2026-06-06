# OpenAI Admin Auth

Auth model recorded for the live cycle; this connector ships the **parse surface** only
(live REST poll deferred).

- Default trust tier: T1 (read) / ACTIVE (poll).
- **No webhook**: OpenAI publishes no webhooks for audit logs — ingestion is an outbound REST
  poll, so there is no signed inbound surface and no `verify()`.
- **Active fetch auth (deferred)**: `GET /v1/organization/audit_logs` requires an **Admin API key**
  (`Authorization: Bearer $OPENAI_ADMIN_KEY`), creatable only by an Organization Owner and usable
  only on admin endpoints. Org-level logging must be enabled in Data Controls (irreversible once on).
  Cursor pagination (`limit`/`after`/`before`) + filters (`event_types`, `effective_at`, `project_ids`).
  Resolved by the operator runtime, never stored here.

## Privacy / PII

- Audit events carry **actor identity** (`actor.session.user.email`, `actor.api_key.user.email`,
  `actor.session.ip_address`, user ids). **FX-SEC-001 screens secret/PHI/PAN only — not a generic
  email or IP — and `redact()` does not scrub IPv4.** The **sole control** is parse-time exclusion:
  the connector **never reads** the actor email / id / ip_address; only the non-PII `actor.type`
  enum is surfaced (allowlisted to `session`/`api_key`).
- Per-actor attribution (filtering by `actor_emails`/`actor_ids`) is deferred behind the PII
  redaction-and-pass model.

## Expected secret keys (operator runtime)

- `admin_api_key` — the org Admin API key (Bearer) for the deferred REST poll.

## Live path — reference poll client (recorded-fixture-proven)

The request-construction + cursor pagination are **built** in `runtime/poll_specs.py`
(`build_openai_admin_spec`) and proven against recorded fixtures (`Authorization: Bearer`;
`data` envelope; `has_more`+`last_id` re-sent as `after`). The real network call + admin-key
resolution remain operator-run.

- **Secret resolver key**: the operator's `SecretResolver` resolves the key by the connector
  **`source_id`** (`openai_admin`); the `admin_api_key` name above is the credential's *meaning*,
  not the lookup key.
- **Assumptions to confirm before live-network wiring** (verify-before-cite): the **`data`** envelope
  key and the response-side cursor (`has_more` + `last_id` re-sent as `after`) are per the OpenAI list
  *convention* — `auth.md` above documents only `limit/after/before`; confirm for this endpoint.
  `items` is a config callable and `next_param` is an argument (not baked as fact).

## Deferred live paths

- Live REST poll of `/v1/organization/audit_logs` + admin-key resolution (the `runtime/` poll client
  is built; the operator supplies the live transport + secret + assumption confirmation).

Credentials are resolved by the operator runtime, never stored in this package.
See [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
