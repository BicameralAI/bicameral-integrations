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
| `GatewaySink` | **#109-gated stub** — `emit` raises `GatewayEmissionGated`. The `AdapterEmission → protocol/schemas/v1/` field mapping is pinned at the **Live** stage (gated on bicameral-bot #109). |
| `SecretResolver` (Protocol) | `resolve(connector_id) -> str` — operator supplies the real keyring-backed one. |
| `MappingSecretResolver` | Reference resolver over an injected mapping (`""` for unknown ids). |
| `deliver_webhook(connector, *, headers, body, sink, …)` | Verify + normalize a webhook delivery, emit, return the emission count (0 on reject/dedup). |
| `deliver_poll(connector, payloads, *, sink, …)` | Parse + normalize a batch of polled payloads, emit, return the count. |

## Readiness ladder (ADR-0012)

`Candidate → Prototype → Beta → Live`. **Beta** = a connector proven end-to-end
through this layer against a reference sink (`CollectingSink`), with **zero
cross-repo dependency**. **Live** (emission to the gateway) is the only stage gated
on bicameral-bot #109. Linear is the first Beta connector.

## Operator wiring (illustrative)

The operator's host owns the HTTP boundary and secret store; it calls in like so:

```python
from runtime import deliver_webhook, CollectingSink
from connectors.linear.connector import LinearConnector

sink = CollectingSink()                      # swap for a real sink at Live
conn = LinearConnector(secret=resolver.resolve("linear"))
count = deliver_webhook(conn, headers=req.headers, body=req.raw_body, sink=sink)
```

A rejected/dedup'd delivery returns `0` and never touches the sink. A true
emission-contract breach (e.g. a sensitive-data hit, blank excerpt) propagates out
of `normalize` to the operator — it is never silently swallowed.
