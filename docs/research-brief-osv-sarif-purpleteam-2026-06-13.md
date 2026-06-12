# Research Brief — osv + sarif purple-team

**Date**: 2026-06-13
**Analyst**: The Qor-logic Analyst (purple-team workflow `wf_b48dc848`, 4 agents: red penetration-tester → blue security-auditor → per-target verdict)
**Target**: the security-batch flips (osv #182, sarif #183) — the deferred adversarial pass.
**Method**: per connector, a red agent attacked across its attack classes; the SARIF red agent was explicitly
pointed at the **secret-in-message crux** (find a secret shape that slips past BOTH `redact()` AND FX-SEC-001);
each finding blue-verified against source, with wire claims traced to the real serializer (SG-2026-06-13-C).

---

## Executive Summary

**Both connectors = approved-with-fixes; ZERO blocked.** osv: **0 findings (clean)** — its SG-2026-06-04-I
defensive guards held across every wrong-typed/absent field. sarif: **2 confirmed** (1 medium, 1 low). The headline
is candid: aiming the red team at this session's own strongest claim (**SG-2026-06-13-E** — "redact-and-pass
scrubs the secret value") surfaced that the claim **over-generalized**, and that the platform's shared secret
catalog is narrower than the claim implied. That is the point of a purple-team.

| Connector | Findings | Verdict |
|---|---|---|
| **osv** | 0 | approved-with-fixes (clean) |
| **sarif** | 2 (1 medium, 1 low) | approved-with-fixes |

## Findings (blue-verified + boundary-checked, file:line)

### sarif
1. **SARIF-PII-1 — pii_on_wire (medium; boundary: v1-gateway-wire)** — `connectors/sarif/connector.py:40`
   redact-and-passes `message.text`, but `redact()` and FX-SEC-001 share **one catalog** —
   `adapter/core/sensitive.py:41-53 _SECRET_PATTERNS` — which covers only **AWS `AKIA`, classic GitHub `ghp_`,
   Azure-storage, PEM, JWT**. A scanner finding quoting a **non-catalog** token — **Slack `xoxb-`, Google API key
   `AIza…`, GitHub fine-grained `github_pat_…`, Stripe `sk_live_…`, GitLab `glpat-…`, npm `npm_…`** — is scrubbed
   by NEITHER `redact()` (no pattern) NOR FX-SEC-001 (no pattern), so it reaches the **gateway wire verbatim**
   (`runtime/gateway_mapping.py:49,61` — description + `evidence[].excerpt`). The AKIA example used to justify
   SG-2026-06-13-E happens to be covered; the **claim implied universal coverage it does not have**. **Fix
   (fleet-wide):** extend `_SECRET_PATTERNS` with the common scanner-emitted token families — both `redact_catalog`
   (the scrub) and `detect_sensitive` (the screen) reuse the tuple, so every connector gains coverage at once.
   **Scope the docs honestly**: redact-and-pass scrubs the *catalog* secret formats (now broadened), not "any
   secret value"; a high-entropy token with no recognizable prefix (e.g. a bare 40-char AWS *secret* key) remains
   a **documented residual** (FX-SEC-001 cannot regex it without false positives) — mirrors the bare-national-phone
   residual. Reachable by ingesting a scanner report whose finding text quotes such a token.
2. **SARIF-PARSE-1 — parse_robustness (low; boundary: none/availability)** — `connectors/sarif/connector.py:61-64`
   `parse_sarif` iterates `report.get("runs") or []` and calls `parse_result(result)` per item with no isinstance
   guard. A **truthy non-list `runs`/`results`** (a dict → iterates keys → `run.get` on a `str`) or a **non-dict
   `result`** raises `AttributeError` that drops **every** finding in the report, not just the bad row (the
   runtime `_PARSE_SKIP` catches it at the whole-payload level → zero emissions instead of N−1). **Fix:** make
   `parse_sarif` per-result resilient — isinstance-guard `runs`/`results` as lists and skip a non-dict `run`/
   `result` (the #59 per-row resilience), so the valid findings still emit while one bad row is dropped.

### osv — clean
No confirmed findings. `parse_vuln` + the `_as_list`/`_text`/isinstance helpers (SG-2026-06-04-I) defended every
wrong-typed/absent OSV field; summary/details redact-and-passed; opaque id floor; metadata is technical; no actor.

## Recommendations (one governed remediation cycle after this brief; modular-commit → PR → merge-if-green)

1. **PT-sarif — secret-catalog breadth + parse resilience + honest scoping (both findings + the fleet-wide gap):**
   (a) extend `adapter/core/sensitive.py:_SECRET_PATTERNS` with curated, prefix-anchored scanner token families
   (Slack/Google/GitHub-fine-grained/Stripe/GitLab/OpenAI/npm) — low false-positive, gains both `redact()` and
   FX-SEC-001 fleet-wide (MEASURE: the full suite must stay green — a too-broad pattern false-positives on existing
   emissions, SG-2026-06-05-F); (b) make `parse_sarif` per-result resilient (SARIF-PARSE-1); (c) scope
   SG-2026-06-13-E + the sarif `config.json`/`references.md`/docstring to "scrubs the catalog secret formats (now
   incl. Slack/Google/Stripe/…)" + record the unbounded-entropy residual. Regression tests: a Slack/Google/Stripe
   token in a finding message is now scrubbed-or-screened; a `[valid, non-dict]` results list yields one
   Observation, not zero.

## Updated Knowledge (Shadow Genome)

- **SG-2026-06-13-F** — *"redact-and-pass scrubs the secret" is only as strong as the secret CATALOG; point the
  red team at your own strongest claim.* SG-2026-06-13-E asserted redact-and-pass keeps a security finding while
  scrubbing the secret value — true only for the catalog formats (`_SECRET_PATTERNS`: AWS/GitHub-classic/Azure/
  PEM/JWT). A scanner can emit Slack/Google/Stripe/GitLab/npm/GitHub-fine-grained tokens that slip past BOTH
  `redact()` and the FX-SEC-001 screen (both reuse the one catalog) and reach the wire verbatim. **Rule:** a
  redaction/screen claim must name the catalog it depends on and state the residual; broaden the *shared* catalog
  (it fixes scrub + screen + every connector at once) rather than patching one connector; and an unbounded
  high-entropy secret with no recognizable prefix is a permanent regex residual to disclose, not to over-claim
  away. Reinforces SG-2026-06-13-E (which this corrects), SG-2026-06-12-B (sweep the shared surface).

---

_Recon complete. osv clean; sarif cleared with one medium (fleet-wide secret-catalog breadth) + one low (parse
resilience), plus an honest scoping of SG-2026-06-13-E. EM-safe + read-only + ADR-0012 + the data-minimization
core (snippet never read) all hold._
