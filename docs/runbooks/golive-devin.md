# Go-Live Runbook — Devin

**Status:** flip-ready, NOT yet Live · **Mode:** active v3 poll (no webhooks) · **Trust:** T1
**Descriptor:** `connectors/devin/config.json` · **Backend:** `connectors/devin/SETUP.md` · **Auth facts:** `connectors/devin/auth.md`

Polls the Devin **v3 enterprise** sessions API (`GET /v3/organizations/{org_id}/sessions`) and emits each session as redacted, governed evidence. Cursor pagination (`end_cursor`/`has_next_page` → `after`); list wraps under `items`; PRs under `pull_requests[]`.

## Credentials + config

| Key | What | Where to get it |
|---|---|---|
| `devin` | Service-User API key (`cog_…`, Bearer) | Devin org settings → API keys (shown once; RBAC-scoped) |

`base_url` is **required runtime config** (no default) — the operator templates the org id in:

```json
{
  "connectors": { "devin": {
    "enabled": true,
    "secrets": { "devin": "<cog_ Service-User key>" },
    "runtime": { "base_url": "https://api.devin.ai/v3/organizations/<org_id>/sessions" }
  }},
  "gateway": { "endpoint": "https://<your-bot>/api/v1/external-ingest", "token": "<ingest token>" }
}
```
(or `BICAMERAL_DEVIN` for the key). `base_url` must be **https** (enforced).

## Live-flip steps

1. **Place** the `cog_` key + `base_url` (with your real `org_id`) as above.
2. **Dry-run (local sink):** `python -m runtime.cli run devin` → prints screened session emissions. Confirm recent sessions appear; the excerpt is `[status] title structured_output` **redacted**; the first `pull_requests[].pr_url` is the artifact location.
3. **Live test:** `python -m runtime.cli run devin --sink gateway` → expect 201 per session.

## Wire gates to confirm against the live response — IMPORTANT (v1 vs v3)

- **Target the v3 ENTERPRISE API** (`docs.devinenterprise.com`): `items` envelope, `pull_requests[]` of `{pr_url, pr_state}`, cursor `end_cursor`/`has_next_page`/`after`, Bearer `cog_`. Re-verified live 2026-06-11 = MATCH.
- **Do NOT** point `base_url` at the parallel **v1** API (`docs.devin.ai`: `GET /v1/sessions`, `sessions` envelope, singular `pull_request`, limit/offset, `apk_` keys) — that shape is the 2026-06-08-corrected drift and would ingest zero/wrong (SG-2026-06-11-A). Confirm your `org_id`-templated v3 URL returns an `items` array.

## Promote / rollback

- **Promote to Live** when a real poll returns recent sessions at 201 with redacted excerpts + correct PR artifact URLs. Operator decision.
- **Rollback:** remove `gateway.endpoint` or `enabled: false`; rotate the `cog_` key in Devin.

## Security notes for the live test (purple-team #133)

Session free-text (title/structured_output) is redact-and-passed (`adapter.core.redaction.redact`); the wire `source` (pr_url) is additionally redacted for email/phone. Non-string scalar session fields are type-guarded (no crash). Redirects not followed; aggregate cap (50k) across pages. Residual accepted-risk: within-field `order_id: <PAN>` suppression (see runbooks README).
