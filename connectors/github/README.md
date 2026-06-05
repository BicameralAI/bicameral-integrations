# GitHub Connector

Provider-facing GitHub adapter.

## Modes

- **Active** — a GitHub pull-request object maps to one neutral `Observation`
  (`parse_pull_request`).
- **Webhook** — a pull-request event is an envelope (`{action, number,
  pull_request:{…}, repository}`); `normalize_event` rebuilds the flat PR object
  `parse_pull_request` expects (injecting the top-level `number`) before parsing.

`X-Hub-Signature-256` (hex HMAC-SHA256 over the raw body, `sha256=`-prefixed)
verification and best-effort `X-GitHub-Delivery` dedup are implemented in
`verify()` / `normalize_event()`. The live `fetch_active` REST path and secret
resolution stay in the operator runtime (see [`auth.md`](auth.md)).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its signed-webhook → `runtime.deliver_webhook` → reference
sink path is proven end-to-end by `runtime/tests/test_runtime.py` (the test
asserts the PR `number` survives the envelope unwrap), with **zero cross-repo
dependency**. Live (gateway emission) is now operator-actionable — `GatewaySink` is real (bot #109 landed, PR #131); an operator configures it against a real gateway to go Live.

## Surface

- `parse_pull_request(payload)` — GitHub PR → `Observation` (PR `body` → excerpt,
  with `title` fallback; `base.repo.full_name#number` → ref; `html_url` → ref
  url; `user.login` → author; `merged_at` → timestamp).
- `GitHubConnector` — connector identity, capabilities (`ACTIVE`, `WEBHOOK`),
  `verify()`/`normalize_event()`; `can_handle_ref` routes by `source_id` or a
  parsed `github.com` host.

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
