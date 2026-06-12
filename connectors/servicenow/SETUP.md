<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# ServiceNow — backend setup

ServiceNow ITSM incidents (Table API) as redact-and-pass governed evidence.

- **id** `servicenow` · **version** 0.1.0 · **channel** beta · **category** itsm · **trust tier** T1
- **status** live-ready · **available** True · **modes** active

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `servicenow` — Integration-user password (basic, required)
- Wire format: `Authorization: Basic (integration username:password)`
- Serves run mode(s): `active`
- Supply via config key `servicenow` **or** env `BICAMERAL_SERVICENOW` (env wins when set).
- Where to get it: https://docs.servicenow.com/bundle/xanadu-platform-administration/page/integrate/inbound-rest/concept/c_TableAPI.html
  - Create a dedicated integration user with `rest_service` + the incident table-read roles (least privilege).
  - The password is the resolved secret; the instance host + username are non-secret runtime config (below).

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "servicenow": {
      "enabled": true,
      "secrets": {
        "servicenow": "<Integration-user password>"
      },
      "runtime": {
        "instance": "<ServiceNow instance host>",
        "username": "<Integration-user username>",
        "limit": 100,
        "fields": "<sysparm_fields (comma list)>"
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `instance` | True | — | Bare hostname, e.g. acme.service-now.com (host-validated before the URL is built; no path/query injection). |
| `username` | True | — | Non-secret Basic-auth username for the integration user (paired with the resolved password). |
| `limit` | False | 100 | Rows per page; sysparm_offset advances by this until a short page (offset pagination). |
| `fields` | False | — | Optional field selection (urlencoded; cannot inject sibling query params). |

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run servicenow                 # fetch -> print screened emissions
python -m runtime.cli run-mods servicenow --mods dependency_risk
python -m runtime.cli run servicenow --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: incident
- PII posture: Incident description/short_description are free-text that routinely carry secrets/PII -> passed through adapter.core.redaction.redact (redact-and-pass: scrubs secret/PHI/PAN + email/phone). The caller_id/caller identity field is NEVER read. number/state/priority are the non-PII metadata surface. FX-SEC-001 is the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + redact-and-pass surface + the live fetch-half (build_servicenow_spec, Basic + offset pagination) are built and harness-proven against recorded 2-page fixtures; the SSRF-4 URL-injection gap is fixed (#133). Gated on operator review + a live poll with a real integration-user credential. To flip: provide the password + instance + username; wire GatewaySink; run the live poll; review before promoting.

- Gate: Table API documented shape: GET https://<instance>/api/now/table/incident, HTTP Basic, `{result:[...]}` envelope, sysparm_offset/sysparm_limit offset pagination (stop-on-short-page). instance is host-validated + the URL is urllib-built (SSRF-4 fix, #133) so instance/fields cannot inject host/path/query.
- Gate: OAuth 2.0 is a deferred alternative; Basic auth this cycle.
- Gate: Live flip gated on operator human review + a live Table-API poll with a real integration-user credential (ADR-0012).

## References

- api: https://docs.servicenow.com/bundle/xanadu-platform-administration/page/integrate/inbound-rest/concept/c_TableAPI.html
