# ServiceNow Auth

Auth model recorded for the live cycle; this connector ships the **parse + redaction
surface** only (live REST poll deferred).

- Default trust tier: T1 (read) / ACTIVE (poll).
- **No webhook**: ServiceNow table reads have no first-party webhook here — ingestion is an
  outbound REST poll against a per-tenant instance, so there is no signed inbound surface and
  no `verify()`.
- **Active fetch auth (deferred)**: the Table API (`GET https://<instance>.service-now.com/api/now/table/incident`)
  uses **Basic auth** or **OAuth 2.0** with a dedicated integration user holding `rest_service`
  + the table-read roles (least privilege). `sysparm_fields` / `sysparm_limit` / `sysparm_offset`
  scope and page the read. Resolved by the operator runtime, never stored here.

## Privacy / PII

- The incident `description` / `comments` / `work_notes` are free-text that routinely carry
  secrets/PII, so the description is passed through `adapter.core.redaction.redact`
  (**redact-and-pass**: scrubs secret/PHI/PAN + email/phone so the emission passes the FX-SEC-001
  hard screen; FX-SEC-001 remains the un-bypassable backstop).
- The **`caller_id` / `caller`** identity field is **never read** (PII).
- `short_description` is also passed through `redact` defensively; `number`/`state`/`priority`
  are the non-PII metadata surface.

## Expected secret keys (operator runtime)

- `instance` — the ServiceNow instance host.
- `username` + `password` (Basic) or `oauth_*` (OAuth 2.0) for the integration user.

## Deferred live paths

- Live Table API poll (`/api/now/table/incident`) + auth resolution + `sysparm` pagination.

Credentials are resolved by the operator runtime, never stored in this package.
See [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
