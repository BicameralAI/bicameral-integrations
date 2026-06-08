# Connectors

Connectors are provider-facing components. They know external APIs, auth flows,
pagination, retries, webhook signatures, and provider-native ids.

Each connector exposes a small **parse surface** — one or more
`parse_*(payload) -> Observation` functions plus a `<Provider>Connector` class
declaring its `source_id` and supported modes. Connectors return raw or lightly
structured provider observations; the [universal adapter](../adapter/README.md)
turns those observations into Bicameral emissions via `pipeline.normalize()`.
Connectors are read-only evidence adapters — they never write canonical state
(ADR-0008).

Live network, auth, and webhook-signature paths are deferred per connector and
documented in each connector's `auth.md`; the implemented surface this cycle is
payload parsing, exercised against synthetic fixtures.

## Index

**Readiness ladder** (ADR-0012): `Candidate → Prototype → Beta → Live`. **Beta**
= proven end-to-end through the [`runtime/`](../runtime/README.md) harness
(ingest → verify → normalize → emit) against a reference sink, with zero
cross-repo dependency. **Live** (gateway emission) is now operator-actionable — `GatewaySink` is real (bot #109 landed, PR #131); an operator configures it against a real gateway to go Live.

"Verify" = webhook signature verification (`verify()`/`normalize_event()` HMAC +
dedup) is wired; "—" = parse-only or live verification deferred.

| Connector | Status | Modes | Surface | Verify |
|---|---|---|---|---|
| [github](github/) | **Beta** | active, webhook | `parse_pull_request` | ✓ (HMAC, `sha256=`) |
| [fathom](fathom/) | **Beta** | passive, webhook | `parse_meeting` | ✓ (Svix) |
| [linear](linear/) | **Beta** | webhook, active | `parse_event` | ✓ (HMAC + 60s replay) |
| [granola](granola/) | **Beta** | passive | `parse_transcript` | — (poll; **live-poll client built**) |
| [local_directory](local_directory/) | **Beta** | passive | `parse_file` | — |
| [google_drive](google_drive/) | **Beta** | active | `parse_document` | — |
| [sarif](sarif/) | **Beta** | passive | `parse_sarif` / `parse_result` | — |
| [slack](slack/) | **Beta** | webhook | `parse_message` | ✓ (v0 + 5m replay) |
| [notion](notion/) | **Beta** | active, webhook | `parse_page` | ✓ (HMAC, `sha256=`) |
| [mcp_registry](mcp_registry/) | **Beta** | active | `parse_server` | — (poll; **live-poll client built** — public no-auth `GET /v0/servers`, cursor-paginated) |
| [continue_dev](continue_dev/) | **Beta** | passive | `parse_event` | — |
| [aider](aider/) | **Beta** | passive | `parse_commit` | — |
| [claude_code](claude_code/) | **Beta** | passive | `parse_session_line` | n/a (local file) |
| [osv](osv/) | **Beta** | active | `parse_vuln` | n/a (no-auth) |
| [sentry](sentry/) | **Beta** | webhook | `parse_issue` | ✓ (HMAC) |
| [pagerduty](pagerduty/) | **Beta** | webhook | `parse_event` | ✓ (multi-sig) |
| [jira](jira/) | **Beta** | webhook, active | `parse_issue` | ✓ (HMAC, `sha256=`) |
| [zendesk](zendesk/) | **Beta** | webhook, active | `parse_ticket` | ✓ (Base64 HMAC) |
| [gitlab](gitlab/) | **Beta** | webhook, active | `parse_merge_request` / `parse_issue` | ✓ (shared token) |
| [confluence](confluence/) | **Beta** | active, passive | `parse_content` | — |
| [copilot](copilot/) | **Beta** | active | `parse_metrics_day` | — (poll; **live-poll client built**; aggregate/PII-free) |
| [cursor](cursor/) | **Beta** | active | `parse_usage_day` | — (poll; **live-poll client built** (Basic+POST); PII dropped) |
| [devin](devin/) | **Beta** | active | `parse_session` | — (poll; **live-poll client built** (1st page); body redacted) |
| [servicenow](servicenow/) | **Beta** | active | `parse_incident` | — (poll; **live-poll client built** (Basic+offset); redact-and-pass) |
| [openai_admin](openai_admin/) | **Beta** | active | `parse_audit_log` | — (poll; **live-poll client built**; actor dropped) |
| [anthropic_admin](anthropic_admin/) | **Beta** | active | `parse_usage` | — (poll; **live-poll client built** — `runtime/poll_client.py`, recorded-fixture-proven; aggregate/PII-free) |

Candidate selection and trust tiers are tracked in the
[Integration Candidate Catalog](../docs/INTEGRATION_CANDIDATE_CATALOG.md) and the
[Trust Tier Model](../docs/TRUST_TIER_MODEL.md).
