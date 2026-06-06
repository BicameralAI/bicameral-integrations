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

## Live path — reference poll client (recorded-fixture-proven)

The request-construction + **offset pagination** are **built** in `runtime/poll_specs.py`
(`build_servicenow_spec`) and proven against recorded 2-page fixtures (HTTP **Basic**; `{result:[…]}`
envelope; `sysparm_offset` advances by `sysparm_limit`, stops on a short page). The real network call
+ auth resolution remain operator-run.

- **Secret resolver key**: the `SecretResolver` resolves by the connector **`source_id`**
  (`servicenow`) → the **password**. `instance` (host) and `username` are **non-secret operator
  config** passed to `build_servicenow_spec(instance=…, username=…)`, not resolved as secrets.
- **Assumptions / scope**: the `{result:[…]}` envelope + `sysparm_offset`/`sysparm_limit` are the
  documented Table-API shape (kept a config callable). **OAuth 2.0 is a deferred alternative** —
  Basic auth this cycle.

## Deferred live paths

- Live Table API poll (`/api/now/table/incident`) + auth resolution (the `runtime/` poll client is
  built — Basic + offset pagination; the operator supplies the live transport + password; OAuth is a
  deferred alternative).

Credentials are resolved by the operator runtime, never stored in this package.
See [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
