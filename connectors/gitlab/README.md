# GitLab Connector

Read-only evidence connector: it verifies and parses GitLab merge-request and
issue webhooks into neutral `Observation`s. **Status: Beta** (ADR-0012; catalog
source-control, priority P1, default trust tier T1/T3). A source-control adapter
from the
[Integration Candidate Catalog](../../docs/INTEGRATION_CANDIDATE_CATALOG.md).

## Modes

- **Webhook** — a GitLab `Merge Request Hook` / `Issue Hook` delivery maps to one
  neutral `Observation` (`parse_merge_request` / `parse_issue`), selected by the
  payload's `object_kind`, with token verification wired
  (`verify()`/`normalize_event()`). Read-only evidence; no canonical writes (ADR-0008).
- **Active** — REST `GET /projects/:id/merge_requests/:iid` (and issues) returns
  the same `object_attributes`-shaped fields (live REST poll fallback, deferred).

## Readiness: Beta (ADR-0012)

Promoted to **Beta**: its token-signed-webhook → `runtime.deliver_webhook` →
reference sink path is proven end-to-end by `runtime/tests/test_runtime.py`, with
**zero cross-repo dependency**. The fail-closed negative (wrong / missing
`X-Gitlab-Token` → zero emissions) is proven in the same harness. Live (gateway
emission) is now operator-actionable — `GatewaySink` is real (bot #109 landed,
PR #131); an operator configures it against a real gateway to go Live.

## Surface

- `parse_merge_request(event)` — GitLab `merge_request` event → `Observation`.
  `object_attributes.description` → excerpt (falling back to `title`, then a
  `gitlab-merge-request` terminal floor); `project.path_with_namespace!iid` → ref
  (GitLab's MR `!` notation); `object_attributes.url` → ref url; `user.username`
  → author; `kind="merge_request"`.
- `parse_issue(event)` — GitLab `issue` event → `Observation`; same mapping with
  `#iid` ref notation and `kind="issue"`.
- `GitLabConnector` — identity + capabilities (`WEBHOOK`, `ACTIVE`); `observations()`
  dispatches on `object_kind` (unknown kinds → `[]`); `verify()` checks the
  plaintext `X-Gitlab-Token` shared secret (constant-time, fail-closed);
  `normalize_event()` self-guards + best-effort dedup (`X-Gitlab-Event-UUID`).

## Verification

GitLab does **not** HMAC-sign the payload like GitHub — it sends the configured
secret verbatim in the `X-Gitlab-Token` header. `verify()` delegates to
`adapter.core.webhook_security.verify_shared_token` (constant-time plaintext
equality; fail-closed on missing/blank/mismatch; the secret/token is never echoed
into an error). The newer Standard-Webhooks *signing token* path is a documented
future enhancement — see [`auth.md`](auth.md).

## References

- Auth model (deferred): [auth.md](auth.md)
