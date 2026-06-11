# Bicameral Integrations — Capability Matrix

Bicameral Integrations is a **governed, read-only evidence layer** for your engineering and work tools. It connects to the systems your teams already use, converts each source's native data into one neutral, reviewable evidence object, screens every object for sensitive data, and hands that evidence to the Bicameral review workflow. It is an **evidence adapter, not a state authority** — it never writes back to your systems and never makes a binding decision on its own.

Three pieces compose it: a **Universal Adapter** (the normalization seam and security spine), **Connectors** (the sources), and **Mods** (advisory governance signals over the evidence).

> **Activation model.** Every connector below is **flip-ready**: the parse, verification, and ingestion paths are built and hardened. To activate ("flip") one, the operator supplies their own credentials and wires their own gateway endpoint. Secrets are never stored in Bicameral — they are resolved at runtime by the operator's environment.

---

## The Universal Adapter

**One contract, any source.** Every connector emits the same neutral shape — an `Observation` → `AdapterEmission` — so everything downstream handles a single format no matter where the data came from. Each emission carries *reviewable evidence*: an excerpt plus a stable source reference (id, URL, kind, timestamp).

**Three connection modes:**

- **Webhook** — the source pushes a cryptographically signed event.
- **Active** — Bicameral polls the source's API on demand.
- **Passive** — operator-run ingestion.

**The security spine — applied to every source:**

- **Hard sensitive-data screen.** Every emission is scanned field-by-field. Any object carrying a **secret, health identifier (PHI), or payment-card number (PAN)** is **rejected outright** and never forwarded. This gate is never bypassed.
- **Redact-and-pass.** Free-text bodies (PR descriptions, transcripts, messages, tickets) are scrubbed of secrets/PHI/PAN **plus email addresses and phone numbers (US and international formats)** before emission — so useful context flows through as evidence without carrying PII.
- **Identity minimization.** Human real names are dropped; only opaque, pseudonymous identifiers (e.g. a vendor user-id) are surfaced for attribution.
- **Signed-webhook verification.** Webhook deliveries are verified with constant-time HMAC checks, with replay protection and delivery de-duplication.
- **Credential & request hardening.** Credentialed polls are pinned to each provider's verified host (anti-SSRF), redirects are not followed, private/internal/cloud-metadata addresses are denylisted, and result volume is capped. Failures fail **closed** — no request, no partial leak.
- **Read-only by design.** Adapters never write canonical state back to a source.
- **Independently hardened.** The connector and adapter code has been through multiple adversarial "purple-team" security reviews under a governed development process.

---

## Connector Capability Matrix

**12 flip-ready connectors.**

| Connector | Category | Mode | Data in | Data out (neutral evidence) | Security & PII handling |
|---|---|---|---|---|---|
| **Linear** | Project mgmt | Webhook + Active | Linear issues / issue events | `issue` — identifier, title, description, URL | `Linear-Signature` HMAC-SHA256 verify; GraphQL fetch host-pinned to `api.linear.app`; actor's real name dropped |
| **Google Drive** | Docs | Active | A Google Doc | `document` — title + body text | OAuth Bearer (operator-refreshed); fixed Google Docs host; document id strictly validated; hard screen backstop |
| **Devin** | Developer-AI | Active | Devin coding sessions | `session` — redact-and-passed free text | Bearer service-user key; host-pinned to `api.devin.ai` |
| **Cursor** | Developer-AI | Active | Per-developer daily usage rows | `usage_metrics` — **PII-free** aggregate counts + opaque user-id | HTTP Basic; host-pinned to `api.cursor.com`; email/name **never read** (strict non-PII allowlist) |
| **GitHub Copilot** | Developer-AI | Active | Org-level aggregate metrics | `usage_metrics` — **PII-free**, no per-person data | Bearer (`read:org`); host-pinned to `api.github.com` |
| **ServiceNow** | ITSM | Active | ServiceNow incidents | `incident` — redact-and-passed summary/description | HTTP Basic; instance host injection-validated **and** denylisted against private/cloud-metadata targets; caller identity never read |
| **Granola** | Meetings | Passive | Meeting notes + transcript | `transcript` — redact-and-passed; owner identity dropped | Bearer key; host-pinned to `public-api.granola.ai` |
| **MCP Registry** | Agent ecosystem | Active | Public MCP server registry | `mcp_server` — redact-and-passed public text | No credential (public data); third-party free text redact-and-passed |
| **GitHub** | Source control | Webhook | Pull-request events | `pull_request` — redact-and-passed body + title; public author login | `X-Hub-Signature-256` HMAC-SHA256, constant-time, verify-before-parse; delivery de-dup with body-hash fallback |
| **Jira** | Project mgmt | Webhook | Issue created/updated/deleted | `issue` — redact-and-passed summary; rich-text body never read; actor dropped | `X-Hub-Signature` HMAC-SHA256 (WebSub); delivery de-dup |
| **Slack** | Communication | Webhook | Slack messages | `message` — redact-and-passed text; opaque user-id | `X-Slack-Signature` v0 HMAC-SHA256 over `v0:{timestamp}:{body}` with a **5-minute replay window** |
| **Notion** | Docs | Webhook | Page-change events | Page-changed **pointer** keyed by the stable page id (signals *what changed*) | `X-Notion-Signature` HMAC-SHA256 over the body; delivery de-dup with body-hash fallback |

---

## Governance Mods

Mods read the neutral evidence stream and emit **advisory signals only** — annotations, review-routing hints, suggested review questions, owner-lens hints. They are strictly **non-authoritative**: a mod can never write a decision, approve or sign off, resolve compliance, block CI, mutate evidence, or assign a reviewer. Every mod output passes the same hard sensitive-data screen.

**13 advisory mods.**

| Mod | What it surfaces |
|---|---|
| **Dependency Risk** | Dependency vulnerabilities + dependency-manifest changes |
| **Data Classification** | Confidentiality markers / sensitive-data classification cues |
| **Security Mentions** | Security-keyword mentions (complements, never replaces, the hard screen) |
| **Noisy Source Gate** | High-noise sources that warrant a manual review gate |
| **Adapter Contract** | Evidence-shape defects — a lost source pointer, missing evidence |
| **Source Trust Calibration** | Provenance signals (missing actor identity, unknown schema, public source) → keep-advisory routing |
| **Webhook Risk** | Webhook-safety signals (a change naming missing signature/replay protection) |
| **Connector Freshness** | Stale provider assumptions (deprecations, API-version migrations) |
| **Code Review Risk** | PR-level blast radius (schema/auth/CI/secrets/breaking) → review routing + a grounded question |
| **Authority Boundary** | Changes naming an authority-crossing action (auto-merge, bypass-policy, deploy-to-prod, credential-scope) → governance routing |
| **Test Adequacy** | Behavior changes that reference no tests → review routing + a test-gap question |
| **Ownership Routing** | Maps a change to a reviewer lens / domain owner (security, connectors, governance, CI, docs) |
| **Decision Drift** | Evidence that may conflict with a recorded decision → governance routing |

---

## Security & Trust Model

Bicameral Integrations treats every inbound payload as untrusted and every credential as the operator's to control.

- **Sensitive data never reaches the wire.** The hard screen rejects any secret/PHI/PAN; redact-and-pass strips email and phone from free text before it leaves the adapter.
- **Only pseudonymous identity is surfaced.** Real names are dropped at the source.
- **Inbound events are authenticated.** Constant-time HMAC verification, replay windows, and delivery de-duplication on every webhook.
- **Outbound calls are constrained.** Verified-host pinning, no-follow redirects, internal/metadata-address denylists, and capped result volumes — all fail-closed.
- **The boundary is read-only.** Adapters surface evidence; they never write canonical state.
- **Operator-controlled activation.** You own your credentials and your gateway. Bicameral stores no secrets; nothing goes Live until you wire it.
- **Adversarially reviewed.** Connectors, the adapter core, and the mods have each been through multiple purple-team security passes.

---

## Future Development

The following connectors are in **Beta** — their parse surfaces are in development and not yet flip-ready:

Aider · Anthropic Admin (usage) · Claude Code · Confluence · Continue.dev · Fathom · GitLab · Local Directory · OpenAI Admin (usage) · OSV (vulnerabilities) · PagerDuty · SARIF (scan results) · Sentry · Zendesk

---

*Bicameral Integrations turns the tools your teams already use into governed, privacy-screened evidence — one neutral contract, hardened end to end, activated entirely on your terms.*
