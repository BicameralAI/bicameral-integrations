# Go-Live Runbook — Linear

**Status:** flip-ready, NOT yet Live · **Modes:** webhook (primary) + active GraphQL · **Trust:** T1
**Descriptor:** `connectors/linear/config.json` · **Backend:** `connectors/linear/SETUP.md` · **Auth facts:** `connectors/linear/auth.md`

Linear is a two-credential connector: the **active GraphQL fetch** and the **webhook receive** path use different secrets. The headless runner (`runtime.cli run linear`) exercises the **active** path; webhook receipt is operator-runtime.

## Credentials

| Key | What | Where to get it | Serves |
|---|---|---|---|
| `linear` | Personal API key (`lin_api_…`) | linear.app → Settings → API → Personal API keys | active GraphQL |
| `linear_webhook` | Webhook signing secret | linear.app/developers/webhooks (shown when you create the webhook) | webhook receive |

- The API key is sent as a **raw `Authorization` header (NO `Bearer` prefix)** — verified against linear.app/developers/graphql.
- The webhook secret verifies `Linear-Signature` = hex HMAC-SHA256 over the raw body, with a 60s anti-replay window + `webhookId` dedup.

## Live-flip steps

0. **Guided setup (recommended, #227):** `python -m runtime.cli configure linear` walks the
   descriptor's instructions — collects both secrets (masked, `lin_api_` format-checked), the
   webhook receiver URL, runs the verify fetch, and writes the gitignored local config with
   `enabled: true`. Active-only setup: `--modes active` (skips the webhook credential,
   FX-RUNTIME-005). Steps 1-2 below are the manual equivalent; step 3-4 still apply.
1. **Place the secrets** (gitignored `config/bicameral.local.json`, or env):
   ```json
   {
     "connectors": { "linear": {
       "enabled": true,
       "secrets": { "linear": "<Personal API key>", "linear_webhook": "<Webhook signing secret>" },
       "runtime": { "page_size": 50 }
     }},
     "gateway": { "endpoint": "https://<your-bot>/api/v1/ingest", "token": "<ingest token>" }
   }
   ```
   (or `BICAMERAL_LINEAR` / `BICAMERAL_LINEAR_WEBHOOK`). An active run requires only `linear` (mode-scoped, FX-RUNTIME-005).
2. **Dry-run (local sink):** `python -m runtime.cli run linear` → prints screened issue emissions. Confirm recent issues appear, titles/excerpts are sane, no secret/PII printed.
3. **Live test (active):** `python -m runtime.cli run linear --sink gateway` → expect 201 per emission.
4. **Webhook path (operator-runtime):** register a Linear webhook on **Issue** events pointing at your Bicameral receiver URL; inject `linear_webhook` into the receive path; send a signed test webhook → expect exactly one emission, and a replayed/older delivery to be rejected.

## Wire gates to confirm against the live response

- **GraphQL issue field set** `id / identifier / title / description / url / updatedAt / state.name` matches the live `data.issues.{nodes,pageInfo}` envelope (verify-before-cite).
- 200-with-`errors` and 400-`RATELIMITED` are handled (no partial emit).
- Endpoint is **pinned to `api.linear.app`** (hardened) — confirm you are not overriding it.

## Promote / rollback

- **Promote to Live** when the active fetch returns correct issues at 201 AND a signed test webhook produces one emission. Operator decision; descriptor `status` stays `live-ready`.
- **Rollback:** remove `gateway.endpoint` (re-gates emission, `GatewayEmissionGated`) or disable the connector (`enabled: false`). Secrets can be rotated in Linear; nothing is committed.

## Security notes for the live test (purple-team #133)

PII-safe on the active path (no assignee/creator identity surfaced); webhook emits `actor.name` + issue text behind the FX-SEC-001 hard screen. Redirects not followed; aggregate cap (50k) across GraphQL pages; runtime keys allowlisted (an undeclared `endpoint` override is rejected). Residual accepted-risk: within-field `order_id: <PAN>` suppression (see runbooks README).
