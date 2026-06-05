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
| `GatewaySink` | **Live emission** — maps each emission to the v1 `IngestRequest` (`gateway_mapping.py`) and POSTs to a configured `/api/v1/ingest` (stdlib `urllib`). Default-safe (no endpoint → `GatewayEmissionGated`), fail-closed (re-screens at the boundary; only HTTP 201 succeeds; else `GatewayEmissionError`), secret-safe (operator token never logged). |
| `emission_to_ingest_request` | Map an `AdapterEmission` → the pinned v1 `IngestRequest` dict (vendored schema in `runtime/schemas/`). |
| `SecretResolver` (Protocol) | `resolve(connector_id) -> str` — operator supplies the real keyring-backed one. |
| `MappingSecretResolver` | Reference resolver over an injected mapping (`""` for unknown ids). |
| `deliver_webhook(connector, *, headers, body, sink, …)` | Verify + normalize a webhook delivery, emit, return the emission count (0 on reject/dedup). |
| `deliver_poll(connector, payloads, *, sink, …)` | Parse + normalize a batch of polled payloads, emit, return the count. |

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
sink = GatewaySink(endpoint="https://gateway.internal/api/v1/ingest",
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
