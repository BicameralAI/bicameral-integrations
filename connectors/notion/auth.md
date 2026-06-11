# Notion Auth

Stage: **Beta** — `verify()` is built and proven through the `runtime/` harness (the
"Candidate / no live implementation" note was stale).

- Default trust tier: T1/T3.
- **Webhook verification (built, verified 2026-06-08 against developers.notion.com)**:
  `X-Notion-Signature` = `sha256=<hex HMAC-SHA256(verification_token, raw_body)>`.
  `NotionConnector.verify()` reuses `adapter.core.webhook_security.verify_hmac_hex`,
  fail-closed + constant-time; the subscription `verification_token` is the HMAC key.
  - **`sha256=` prefix is REQUIRED** (we pin the provider's one documented form and reject
    bare hex). Note: Notion's docs show the prefix by example only (no explicit normative
    "prefix mandatory" sentence) — pinning it is stricter-than-documented and intentional.
  - **Raw-body decision**: Notion's sample code HMACs `JSON.stringify(body)`; we sign the
    **raw received bytes** (the correct fail-closed choice — avoids a re-serialization
    mismatch). Confirm byte-equality with a real delivery before relying on it at Live.
- Active REST auth (deferred): OAuth / integration token (developers.notion.com/docs/authorization).

## Verification

`NotionConnector.verify()` checks `X-Notion-Signature: sha256=<hex HMAC-SHA256(verification_token,
raw_body)>` (prefix REQUIRED, bare hex rejected), strips the prefix, reuses
`adapter.core.webhook_security.verify_hmac_hex` — fail-closed + constant-time, over the **raw received
bytes**. Replay dedup keys on the webhook EVENT id with a `sha256(body)` fallback. The `sha256=`
prefix is the open wire_gate (confirm against a live delivery; SG-2026-06-12-A). Note (deep-audit
Cycle 3): the webhook body is a thin EVENT envelope — `normalize_event` parses it via `parse_event`
into a page-changed pointer keyed by the page `entity.id`, NOT the full page object.

Credentials are resolved by the operator runtime, never stored in this package.
See [references.md](references.md) and [TRUST_TIER_MODEL](../../docs/TRUST_TIER_MODEL.md).
