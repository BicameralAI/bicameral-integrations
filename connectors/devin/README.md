# Devin Connector

Read-only evidence connector: it parses Devin agentic-coding **session** objects into
neutral `Observation`s, with free-text redacted. **Status: Beta** (ADR-0012; catalog
developer-AI / agentic-coding, priority P1, default trust tier T1).

## Modes

- **Active** — Devin v3 REST `GET /v3/organizations/{org}/sessions` returns session objects
  (`parse_session`). Read-only evidence; no canonical writes (ADR-0008). **Poll-only —
  Devin publishes no webhooks** (the `/messages` endpoint is a deferred richer surface).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its session → `runtime.deliver_poll` → reference sink path is proven
end-to-end by `runtime/tests/test_runtime.py`, with **zero cross-repo dependency**, and the
free-text redaction is proven end-to-end. Live (gateway emission) is now operator-actionable —
`GatewaySink` is real (bot #109 landed, PR #131).

## Surface

- `parse_session(session)` — a Devin v3 session → `Observation`. Excerpt = `redact("[status]
  title: structured_output")`; `session_id` → ref (`devin-…`, `devin-session` floor);
  `pull_request.url` → ref url; `kind="session"`.
- `DevinConnector` — identity + capabilities (`ACTIVE`); `observations()` parses one session.

## Privacy

The session trail (title / `structured_output` / messages) is free-text that may carry
secrets/PII, so **every free-text field is passed through `adapter.core.redaction.redact`**
(scrubs secret/PHI/PAN + email/phone; composes with the FX-SEC-001 hard screen). The
`pull_request.url` is kept un-redacted as the **artifact location** — consistent with the
`github`/`gitlab`/`jira` connectors that emit the PR/issue URL; it is the artifact path, not
free-text evidence. Author/user identity is not read.

## References

- Auth model (deferred): [auth.md](auth.md)
