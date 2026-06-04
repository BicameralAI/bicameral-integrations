# GitHub Connector

Provider-facing GitHub adapter.

## Modes

- **Active** — a GitHub pull-request object maps to one neutral `Observation`
  (`parse_pull_request`).
- **Webhook** — pull-request events carry a PR object of the same shape and
  parse through the same surface.

The live `fetch_active` HTTP path and webhook signature verification are
deferred this cycle (see [`auth.md`](auth.md)); this connector is the parse
surface only.

## Surface

- `parse_pull_request(payload)` — GitHub PR → `Observation` (PR `body` → excerpt,
  with `title` fallback; `base.repo.full_name#number` → ref; `html_url` → ref
  url; `user.login` → author; `merged_at` → timestamp).
- `GitHubConnector` — connector identity and capabilities (`ACTIVE`, `WEBHOOK`);
  `can_handle_ref` routes by `source_id` or a `github.com` url.

## References

- Canonical documentation: [references.md](references.md)
- Auth model (deferred): [auth.md](auth.md)
