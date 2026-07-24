# runtime — operator-runtime boundary (ADR-0012)

A thin, framework-free layer the **operator's host** (an HTTP receiver / cron — not
this library) calls to drive a connector's `ingest → verify → normalize → emit`
path. The repo stays a **library**, not a server: stdlib-only, no web framework, no
live HTTP listener. This layer is the seam an operator wires their host into.

## What's here

| Symbol | Role |
|---|---|
| `EmissionSink` (Protocol) | `emit(emissions)` — where normalized `AdapterEmission`s go. |
| `CollectingSink` | Reference sink: accumulates into `.emissions` (tests + Beta). |
| `GatewaySink` | **Live emission** — maps each emission to the v2 `ExternalIngestEnvelope`, checks Bot's `/api/external-ingest/capabilities` against the vendored version/schema/fingerprint, then POSTs to `/api/v2/external-ingest`. Default-safe, exact-match fail-closed, receipt-required, and token-safe. |
| `emission_to_external_envelope` | Map an `AdapterEmission` → the pinned v2 `ExternalIngestEnvelope` dict (vendored schema in `runtime/schemas/`, bot schema commit pinned in `runtime/schemas/ingest_schema_pin.json`). |
| `SecretResolver` (Protocol) | `resolve(connector_id) -> str` — operator supplies the real keyring-backed one. |
| `MappingSecretResolver` | Reference resolver over an injected mapping (`""` for unknown ids). |
| `deliver_webhook(connector, *, headers, body, sink, …)` | Verify + normalize a webhook delivery, emit, return the emission count (0 on reject/dedup). |
| `deliver_poll(connector, payloads, *, sink, …)` | Parse + normalize a batch of **already-fetched** polled payloads, emit, return the count. |
| `poll(connector, spec, *, transport, sink, …)` | **Live-poll fetch half** — the symmetric counterpart of `deliver_webhook`'s receive side. Constructs the authenticated request, walks pagination through an injected `HttpTransport`, then delegates to `deliver_poll`. Fail-closed + token-safe. |
| `HttpTransport` (Protocol) / `UrllibTransport` | The network seam. Operator-run `urllib` default; tests inject a recorded transport (a mock does not promote a connector to Live). |
| `ApiKeyHeaderAuth` / `BearerAuth` / `BasicAuth` (`poll_auth.py`) | Auth strategies (CR/LF-rejecting raw inputs, token-free errors): api-key-in-header, Bearer, and HTTP Basic (cursor = key-as-username; servicenow = user+password). |
| `PageToken` / `OffsetPager`, `PollSpec` (`poll_client.py`) | Token/cursor pagination + offset pagination (`sysparm_offset`-style); the per-connector spec (`base_url`/`auth`/`items`/`method`/`pagination`/`body`). The provider token is treated as untrusted. |
| `build_*_spec` (`poll_specs.py`) | Per-connector wiring: `anthropic_admin`, `openai_admin`, `copilot`, `devin`, `granola`, `cursor`, `servicenow` — resolve the secret by `source_id`, wire endpoint + auth + pagination (+ POST body where needed). |

## Readiness ladder (ADR-0012)

`Candidate → Prototype → Beta → Live`. **Beta** = a connector proven end-to-end
through this layer against a reference sink (`CollectingSink`), with **zero
cross-repo dependency**. All 18 connectors are Beta. **Live** = an operator wiring
a configured `GatewaySink` against a real gateway (the gateway ingest guards
landed — bicameral-bot #109 / PR #131). The repo delivers the verified seam; the
operator deployment is what earns a connector Live.

## Operator wiring (illustrative)

The operator's host owns the HTTP boundary and secret store; it calls in like so —
with `CollectingSink` at Beta, or a configured `GatewaySink` to go Live:

```python
from runtime import deliver_webhook, CollectingSink, GatewaySink
from connectors.linear.connector import LinearConnector

# Beta: accumulate into a reference sink.
sink = CollectingSink()
# Live: POST each emission to the (now-guarded) gateway. Default-safe + fail-closed;
# the token is operator-injected and never logged.
sink = GatewaySink(endpoint="https://gateway.internal/api/v2/external-ingest",
                   token=resolver.resolve("bicameral-gateway"))

conn = LinearConnector(secret=resolver.resolve("linear"))
count = deliver_webhook(conn, headers=req.headers, body=req.raw_body, sink=sink)
```

A rejected/dedup'd delivery returns `0` and never touches the sink. A true
emission-contract breach (sensitive-data hit, blank excerpt) propagates out of
`normalize` — never silently swallowed. With `GatewaySink`, only HTTP **201** is
success; a gateway rejection (e.g. `429`) raises `GatewayEmissionError(status,
reason)` for the operator to handle; an unconfigured sink raises
`GatewayEmissionGated`.

### Poll connectors — the fetch half (`poll`)

For ACTIVE/poll connectors the operator supplies a transport (the default
`UrllibTransport`, or their own) plus a `SecretResolver`; `poll` constructs the
authenticated request, paginates, and emits:

```python
from runtime import poll, CollectingSink, UrllibTransport, build_anthropic_admin_spec
from connectors.anthropic_admin.connector import AnthropicAdminConnector

spec = build_anthropic_admin_spec(resolver)          # x-api-key + anthropic-version
count = poll(AnthropicAdminConnector(), spec,
             transport=UrllibTransport(), sink=CollectingSink())
```

`poll` is **fail-closed** (non-200 / unparseable / non-object body / non-list items /
poisoned page token / blank secret / `_MAX_PAGES` / `_MAX_RESPONSE` all raise
`PollError`) and **token-safe** (the operator secret never enters an error or log).
The provider response — including the pagination token — is treated as untrusted.

**Auth strategies** (`poll_auth.py`): `ApiKeyHeaderAuth` (api-key-in-header),
`BearerAuth` (`Authorization: Bearer`), and `BasicAuth` (`base64(user:pass)`;
CR/LF-screened on the raw inputs). **Per-connector specs** live in
`runtime/poll_specs.py` — `build_*_spec` helpers that resolve the secret by
**`source_id`** and wire the endpoint + auth + pagination (+ POST body where needed).
Wired this far: `anthropic_admin` (api-key + token pagination), `openai_admin`
(Bearer + `last_id`/`after` cursor), `copilot` (Bearer; top-level JSON array),
`devin` (Bearer; operator-templated `org_id`; pagination deferred), `granola`
(Bearer; `since` watermark operator-side), `cursor` (Basic key-as-username; **POST**
date-range body), `servicenow` (Basic user+password; **offset** pagination). Each
carries **unverified wire assumptions** (envelope key / cursor / body shape) recorded
in its `auth.md` as the gate before real-network wiring. **Deferred** (don't fit the
page-list poll shape): `google_drive` (`documents.get` + OAuth — a per-resource fetch)
and `mcp_registry` (Candidate — no verified contract). **All 7 buildable poll
connectors now have the fetch half.**
