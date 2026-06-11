# Operator Go-Live Runbooks

Step-by-step live-flip walkthroughs for promoting a **flip-ready** connector to **Live**. Each
connector is code-complete, harness-proven, and purple-team hardened (META_LEDGER #133) — the only
remaining step is the operator wiring real secrets + running a live test against the real provider,
then reviewing and promoting. Per ADR-0012, **a mock does not promote a connector to Live; only this
operator-run live test does.** The repo carries no `live` status value — "Live" is this operator act.

| Connector | Mode(s) | Runbook |
|---|---|---|
| Linear | webhook + active GraphQL | [golive-linear.md](golive-linear.md) |
| Google Drive (Docs) | active `documents.get` | [golive-google_drive.md](golive-google_drive.md) |
| Devin | active v3 poll | [golive-devin.md](golive-devin.md) |

## The shared flip pattern (every connector)

1. **Obtain the credential(s)** from the provider (see each runbook's Credentials table).
2. **Place secrets** in the gitignored `config/bicameral.local.json` under
   `connectors.<id>.secrets.<key>`, **or** export `BICAMERAL_<KEY>` env vars (env wins). **Never commit a secret** — the file is gitignored and `runtime` never logs/echoes a value.
3. **Configure the gateway** once: `gateway.endpoint` = your bicameral-bot `/api/v1/ingest` URL, `gateway.token` = the ingest auth token. With no endpoint, `GatewaySink` is **default-gated** (raises `GatewayEmissionGated`) — so you cannot accidentally emit Live.
4. **Dry-run with the local sink first** (no network egress of evidence):
   `python -m runtime.cli run <id>` — prints the screened emissions (never a secret). Confirm count, titles, and that nothing sensitive appears.
5. **Live test**: `python -m runtime.cli run <id> --sink gateway` — a real POST. Expect the gateway to return **201**; `GatewaySink` re-runs the FX-SEC-001 screen at the boundary and accepts only 201.
6. **Confirm the connector's `wire_gates`** (in its `config.json` / `SETUP.md`) against the live response — these are the verify-before-cite items that must hold before you trust the Live path.
7. **Review + promote**: if the live emissions are correct and the gates hold, the connector is Live (an operator decision; the descriptor `status` stays `live-ready`).

## Security posture verified for the live test (purple-team, 2026-06-11)

These hold on every connector's live path (META_LEDGER #133; locked by `tests/redteam/` + `red-team.yml`):

- **No redirect-following at the transport** — a provider 3xx fails closed; the credential is never re-sent cross-host (SSRF-1).
- **FX-SEC-001 hard screen, per-leaf**, over every wire-bound field (title/body/excerpt/source/ref/author/timestamp) + a redact-and-pass scrub of the wire `source` URL/ref (email/phone).
- **Fail-closed parse** on non-200, oversized, deeply-nested (RecursionError), and type-confused bodies.
- **Credentialed endpoints host-pinned**; operator `runtime` keys allowlisted to the descriptor.
- **Aggregate item cap** (50k) across paginated pages; **GatewaySink** errors never reflect the gateway body or carry the token.

## Accepted residual risk (operator-acknowledged)

- **Within-field `order_id: <PAN>` suppression** is deliberately retained: a digit run immediately preceded by an ID label in the **same** field is treated as an identifier, not cardholder data, to avoid false-positives on legitimate order IDs. Cross-field suppression is closed (per-leaf). A real PAN that is *itself* an `order_id` value in one field would be suppressed — accepted as low-likelihood; revisit if a connector surfaces payment-card data.
