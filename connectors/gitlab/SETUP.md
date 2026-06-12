<!-- GENERATED from config.json — do not edit; run scripts/build_connector_setup.py -->
# GitLab — backend setup

GitLab merge-request + issue webhook events as redact-and-pass governed evidence (body + title scrubbed; public username retained as the artifact author).

- **id** `gitlab` · **version** 0.1.0 · **channel** beta · **category** source-control · **trust tier** T1
- **status** live-ready · **available** True · **modes** webhook, active

See [docs/CONNECTOR_BACKEND_SETUP.md](../../docs/CONNECTOR_BACKEND_SETUP.md) for the general backend model (config, secrets, the runner, go-live, troubleshooting).

## Credentials

### `gitlab_webhook` — Webhook secret token (webhook_secret, required)
- Wire format: `X-Gitlab-Token (plaintext shared secret, constant-time compared — GitLab does NOT HMAC-sign the body)`
- Serves run mode(s): `webhook`
- **Note:** webhook-*receive* path only — **NOT** consumed by `runtime.cli run` (the active fetch uses the API credential).
- Supply via config key `gitlab_webhook` **or** env `BICAMERAL_GITLAB_WEBHOOK` (env wins when set).
- Where to get it: https://docs.gitlab.com/user/project/integrations/webhooks/
  - When you create the GitLab webhook, set a Secret token; GitLab sends it verbatim in the X-Gitlab-Token header.
  - Bicameral constant-time-compares it to this secret (fail-closed) and dedups on X-Gitlab-Event-UUID (verified 2026-06-13). The newer Standard-Webhooks signing token is the documented stronger next step, not wired this cycle.

### `gitlab` — Access token (active REST poll — deferred) (api_key, optional)
- Wire format: `Authorization: Bearer <personal/project/group access token> (or PRIVATE-TOKEN)`
- Serves run mode(s): `active`
- Supply via config key `gitlab` **or** env `BICAMERAL_GITLAB` (env wins when set).
- Where to get it: https://docs.gitlab.com/ee/api/rest/authentication.html
  - Create a personal/project/group access token with read scope for the deferred REST poll of merge requests / issues.
  - The active REST poll is operator-runtime and DEFERRED this cycle; the webhook is the built + verified path. Wiring needs operator oversight.

## Backend config

Add to your **gitignored** `config/bicameral.local.json` (placeholders shown — fill real values, or set the `BICAMERAL_<KEY>` env vars instead; never commit secrets):

```json
{
  "connectors": {
    "gitlab": {
      "enabled": true,
      "secrets": {
        "gitlab_webhook": "<Webhook secret token>",
        "gitlab": "<Access token (active REST poll \u2014 deferred)>"
      }
    }
  }
}
```
## Webhook setup

- Signature scheme: plaintext shared-secret token in the X-Gitlab-Token header (GitLab does NOT HMAC-sign the body); constant-time compared, fail-closed; no replay-timestamp window -> best-effort dedup on X-Gitlab-Event-UUID, falling back to a SHA-256 body hash when the UUID is absent (so a stripped-UUID replay cannot bypass dedup). The newer Standard-Webhooks signing token (HMAC-SHA256 over webhook-id.webhook-timestamp.body, webhook-signature header) is GitLab's recommended method and the documented stronger next step, not wired this cycle. (header `X-Gitlab-Token`).
- Events: `merge_request`, `issue`
- Bicameral webhook receiver URL (operator-provisioned) — **you provision this inbound URL** (provisioned_by: operator) and register it at the provider.
  - In your GitLab project, add a webhook subscribed to Merge request events + Issue events and set a Secret token.
  - Set the webhook URL to your Bicameral webhook receiver (see receiver below).

## Run it (headless — no UI)

```bash
python -m runtime.cli list
python -m runtime.cli run gitlab                 # fetch -> print screened emissions
python -m runtime.cli run-mods gitlab --mods dependency_risk
python -m runtime.cli run gitlab --sink gateway   # real POST (go-live; default-gated)
```

`--limit N` caps printed emissions. The default sink prints screened emissions (never a secret).

## Data & permissions

- Emits: merge_request, issue
- PII posture: MR/issue SUBJECT (title) + BODY (description) are PII-dense free text -> redact-and-passed (secret/PHI/PAN + email/phone scrubbed to placeholders; the github standard, since FX-SEC-001 backstops only secret/PHI/PAN). The author is the PUBLIC GitLab username (user.username) -- the artifact author, the kept-public-login precedent github set (SG-2026-06-13-B); only username is read, never name or email, and it is NOT redacted. FX-SEC-001 hard-screens secret/PHI/PAN as the un-bypassable backstop.

## Go-live

Readiness: Flip-ready, NOT yet Live. Parse + plaintext X-Gitlab-Token verify + dedup are built and harness-proven; title/description redact-and-passed, public username retained. The active REST poll is deferred (operator-runtime). Gated on operator review + a live delivery. To flip: create the webhook + secret token + a Bicameral receiver URL; wire GatewaySink; send a test delivery; review before promoting. Stronger path: configure a Standard-Webhooks signing token and reuse the existing Svix verifier.

- Gate: Webhook verification re-verified live 2026-06-13 (docs.gitlab.com webhooks): the X-Gitlab-Token plaintext shared secret is GitLab's documented (legacy) method; GitLab does NOT HMAC-sign the body. Built verify_shared_token (constant-time, fail-closed) MATCHES. The Standard-Webhooks signing token (HMAC-SHA256 over {id}.{ts}.{body}) is the recommended stronger next step, not wired.
- Gate: PII: title + description redact-and-passed (secret/PHI/PAN + email/phone); author = public username (user.username, never name/email). FX-SEC-001 backstops secret/PHI/PAN.
- Gate: Webhook RECEIPT + the active REST poll are operator-runtime; the REST poll is DEFERRED this cycle (webhook is the built + verified path). Live flip gated on operator review + a live delivery with a matching token (ADR-0012).

## References

- api: https://docs.gitlab.com/ee/api/
- webhooks: https://docs.gitlab.com/user/project/integrations/webhooks/
- webhook-verify: https://docs.gitlab.com/user/project/integrations/webhooks/#validate-payloads-by-using-a-secret-token
- auth: https://docs.gitlab.com/ee/api/rest/authentication.html
