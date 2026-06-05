# ServiceNow Connector

Read-only evidence connector: it parses ServiceNow ITSM **incident** records into neutral
`Observation`s, with the free-text description redacted and caller identity dropped.
**Status: Beta** (ADR-0012; catalog ITSM / operations, priority P2, default trust tier T1).

## Modes

- **Active** — Table API `GET /api/now/table/incident?sysparm_fields=…&sysparm_limit=…`
  returns incident records (`parse_incident`). Read-only evidence; no canonical writes
  (ADR-0008). **Poll-only — no first-party webhook for table reads** (per-tenant instance).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its incident → `runtime.deliver_poll` → reference sink path is proven
end-to-end by `runtime/tests/test_runtime.py`, with **zero cross-repo dependency**, and the
redact-and-pass behaviour is proven end-to-end (a secret in the description is redacted so the
emission **passes** the FX-SEC-001 hard screen instead of being rejected). Live (gateway
emission) is now operator-actionable.

## Surface

- `parse_incident(record)` — a ServiceNow incident → `Observation`. Excerpt =
  `redact(short_description — description)` + ` (state=…, priority=…)`; `number` → ref
  (`servicenow-incident` floor); `kind="incident"`.
- `ServiceNowConnector` — identity + capabilities (`ACTIVE`); `observations()` parses one record.

## Privacy

The incident `description` / `comments` are free-text that routinely carry secrets/PII, so the
description is passed through `adapter.core.redaction.redact` (scrubs secret/PHI/PAN + email/phone;
**redact-and-pass** — composes with the FX-SEC-001 backstop). The **`caller_id` / `caller`
identity is never read**. `short_description`/`state`/`priority`/`number` are the safe metadata
surface (short_description is also redacted defensively).

## References

- Auth model (deferred): [auth.md](auth.md)
