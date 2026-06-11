# Research Brief — go-live sequence live-contract verification (verify-before-cite recovery + notion)

**Date**: 2026-06-12
**Analyst**: The Qor-logic Analyst
**Target**: live re-verification of the go-live cycle sequence connectors — mcp_registry, github, jira, slack (shipped #138/#139/#141/#142) + notion (cycle 6, pre-build).
**Why this brief exists**: the prerequisite verify-before-cite `/qor-research` was run for cursor + granola (#135) but **skipped** for mcp_registry/github/jira/slack — those descriptors were authored off each connector's recorded `references.md`/`auth.md` "verified 2026-06-08" claims, which directly contravenes SG-2026-06-11-D ("a recorded 'verified' claim is not verification; re-fetch the live source"). This brief re-fetches the live provider docs to retroactively establish the documentation foundation and to verify notion BEFORE its descriptor.

---

## Executive Summary

The 4 already-shipped descriptors **re-verify clean against live docs** (no drift) — the recorded contracts were accurate this time. The process gap was real nonetheless (verification was assumed from a stale date, not performed). **notion** is now verified ahead of its build, surfacing **one real gap**: the connector's `verify()` requires a `sha256=` prefix on `X-Notion-Signature` that the live docs do not confirm Notion sends — a granola-class "would-reject-all-deliveries" risk carried as a wire-gate.

## Findings (live, 2026-06-12)

| Connector | Cited contract | Live source | Status |
|---|---|---|---|
| **slack** | `X-Slack-Signature` `v0=`, basestring `v0:{X-Slack-Request-Timestamp}:{body}`, HMAC-SHA256 (signing secret), 5-min replay | docs.slack.dev/authentication/verifying-requests-from-slack | **MATCH** |
| **github** | `X-Hub-Signature-256` `sha256=` HMAC-SHA256 over the raw body with the secret token | docs.github.com/.../validating-webhook-deliveries | **MATCH** |
| **jira** | `X-Hub-Signature` `sha256=` (WebSub `method=signature`) over the body; no anti-replay; `X-Atlassian-Webhook-Identifier`; events `jira:issue_*` | developer.atlassian.com/cloud/jira/platform/webhooks/ | **MATCH** (live confirms `method=signature` WebSub form + the dedup header + no replay window) |
| **mcp_registry** | public no-auth `GET /v0/servers`; `servers` envelope, entry nests under `server`; cursor → `metadata.nextCursor`, no has-more | registry.modelcontextprotocol.io/openapi.yaml | **MATCH** (note: a newer `/v0.1/servers` also exists; `/v0/servers` still served — future option) |
| **notion** | (pre-build) connector implements `X-Notion-Signature` `sha256=` HMAC-SHA256 over raw body with `verification_token` | developers.notion.com/reference/webhooks | **VERIFIED w/ GAP** (see below) |

### notion gap (verify-before-cite caught it)

Live docs: "Every webhook request from Notion includes an `X-Notion-Signature` header, which contains an **HMAC-SHA256 hash of the request body, signed with your `verification_token`**" — body is the **minified JSON**. Event types include `page.content_updated`, `comment.created`, `database.schema_updated`, `page.locked`.

The connector's `verify()` (`connectors/notion/connector.py:92-105`) **requires** the header start with `sha256=` and **rejects a bare-hex value**. The live docs describe the hash but **do not confirm a `sha256=` prefix**. If Notion sends a bare hex digest, `verify()` rejects EVERY real delivery (fail-closed-but-broken → ingest zero) — the same class as the granola/devin drifts. **This is UNVERIFIED and is carried as a `wire_gate`, not asserted.** Also: the connector verifies over the raw received bytes, which match only if the operator's receiver forwards Notion's exact (minified) body without re-serializing — noted.

## Blueprint / process alignment

| Claim | Finding | Status |
|---|---|---|
| The 4 shipped descriptors (mcp_registry/github/jira/slack) cite accurate live contracts | Re-fetch confirms all 4 | MATCH (retroactively validated) |
| verify-before-cite was performed for the whole sequence | It was NOT for the 4 shipped (assumed from a stale date) | **PROCESS DRIFT** → SG-2026-06-12-A |
| notion's `sha256=` prefix on X-Notion-Signature | Not confirmed by live docs | **DRIFT RISK** → wire_gate + confirm live before Live |

## Recommendations

1. **The 4 shipped connectors stand** (live-verified clean) — no corrective cycle needed; this brief is their (belated) documentation foundation. **Confidence: high.**
2. **notion proceeds to its descriptor** on the verified contract, but the `sha256=` prefix assumption is a `wire_gate` (confirm the exact `X-Notion-Signature` format against a live delivery before Live; if bare-hex, the connector's prefix requirement must be relaxed). Apply the platform free-text standard: redact-and-pass the page title; keep the opaque `created_by.id`. **Confidence: high.**
3. **Process:** make verify-before-cite a per-connector MANDATORY first step of every go-live cycle (not assumed from a recorded date). **Confidence: high.**

## Updated Knowledge (Shadow Genome)

SG-2026-06-12-A — verify-before-cite is per-connector and per-cycle; a connector's own recorded "verified <date>" line is NOT verification. Four go-live descriptors shipped on stale recorded claims; a recovery re-fetch confirmed them (lucky, not safe), and the same re-fetch surfaced a real notion signature-format gap. Re-fetch the live source every cycle.

---

_Research complete. The 4 shipped descriptors are validated; notion is cleared to build with one documented wire-gate._
