<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# Confluence — backend setup

Confluence Cloud page content as redact-and-pass governed evidence (title + body scrubbed); authenticated REST poll (the Connect-app-JWT webhook needs a Connect app, deferred).

- **id** `confluence` · **category** docs / knowledge-base · **trust tier** T1
- **status** live-ready · **available** True · **modes** active, passive

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `confluence` — API token (Basic: email + token) (api_key, required)
- Wire format: `Authorization: Basic base64('<email>:<api_token>')`
- Serves run mode(s): `active`, `passive`
- Supply via config key `confluence` **or** env `BICAMERAL_CONFLUENCE` (env wins when set).
- Where to get it: https://developer.atlassian.com/cloud/confluence/rest/v1/intro/
  - Create an Atlassian API token (id.atlassian.com -> Security -> API tokens) for the account that reads the spaces.
  - Bicameral fetches GET /wiki/rest/api/content/{id}?expand=body.storage with HTTP Basic (email:token), host-pinned to your <site>.atlassian.net (verified 2026-06-13). OAuth 2.0 (3LO) is the alternative.

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "confluence": {
      "enabled": true,
      "secrets": {
        "confluence": "<API token (Basic: email + token)>"
      },
      "runtime": {
        "base_url": "<Confluence site base URL>",
        "space": "<Space / content filter>"
      }
    }
  }
}
```

Runtime config:

| key | required | default | description |
|---|---|---|---|
| `base_url` | True | — | Your Atlassian Cloud site, e.g. https://<site>.atlassian.net/wiki. The poll client pins to *.atlassian.net (anti-SSRF; the connector's can_handle_ref matches the host). |
| `space` | False | — | Which spaces/pages the operator runtime polls. Operator-runtime knob. |

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run confluence                 # fetch -> print screened emissions
python -m runtime.cli run-mods confluence --mods dependency_risk
python -m runtime.cli run confluence --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: page
- PII posture: A Confluence page TITLE + flattened storage BODY are PII-dense free text (internal docs, names, emails) -> redact-and-passed (secret/PHI/PAN + email/phone scrubbed, since FX-SEC-001 backstops only secret/PHI/PAN). The page URL is ALSO redact-and-passed because the _links.webui slug carries the page title (purple-team CONF-PII-URL-01); the opaque page id ref is not redacted. RESIDUAL: a URL-encoded email in the title slug (e.g. %40) is not regex-matchable -- the redacted title field is the canonical surface. _strip_storage_html is a lossy flattener (NOT a sanitizer) -- redact() + FX-SEC-001 are the security controls. No author is surfaced. FX-SEC-001 hard-screens secret/PHI/PAN as the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + redact-and-pass are built and harness-proven; title + body redact-and-passed, host pinned to *.atlassian.net. Gated on operator review + wiring the live authenticated REST poll (API-token Basic or OAuth) to a GatewaySink. To flip: create the API token + set the site base URL; wire the runtime poll; fetch a real page; review before promoting. The Connect-app-JWT webhook is a future path (needs a registered Connect app).

- Gate: Cloud signature scheme re-verified 2026-06-13 (Atlassian docs): the Data-Center X-Hub-Signature HMAC does NOT transfer to Cloud; the Cloud webhook scheme is Connect-app JWT (Authorization: JWT, HS256 over the per-tenant install shared secret + qsh binding). It needs a registered Connect app + install-handshake shared-secret store, so verify() stays deferred and the descriptor offers only the authenticated poll (SG-2026-06-14-B).
- Gate: PII: page title + flattened storage body redact-and-passed (secret/PHI/PAN + email/phone); opaque id ref + URL un-redacted; no author. _strip_storage_html is a lossy flattener, not a sanitizer; redact() + FX-SEC-001 are the controls.
- Gate: The live REST fetch (OAuth 2.0 3LO or API-token Basic), host-pinned to *.atlassian.net, is operator-runtime; no live network this cycle. Live flip gated on operator review + a real authenticated page fetch (ADR-0012).

## References

- rest-api: https://developer.atlassian.com/cloud/confluence/rest/v1/intro/
- auth: connectors/confluence/auth.md
