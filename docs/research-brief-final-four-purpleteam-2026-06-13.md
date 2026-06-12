# Research Brief — anthropic_admin + openai_admin + continue_dev + confluence purple-team

**Date**: 2026-06-13
**Analyst**: The Qor-logic Analyst (purple-team workflow `wf_c1e952ab`, 8 agents: red penetration-tester → blue security-auditor → per-target verdict)
**Target**: the final-four flips (anthropic_admin #188, openai_admin #189, continue_dev #190, confluence #191) — the deferred adversarial pass that completes **26/26 connectors purple-teamed.**
**Method**: per connector, a red agent attacked across its attack classes, pointed at each connector's headline CLAIM (PII-free / identity-never-read / lossy-flattener-is-safe); each finding blue-verified against source, wire claims traced to the real serializer (SG-2026-06-13-C).

---

## Executive Summary

**All four connectors = approved-with-fixes; ZERO blocked.** 4 findings confirmed (one per connector), all
low/medium. The headline CLAIMS largely held — anthropic_admin IS PII-free in the surfaced fields, openai_admin
DOES drop actor email/id/IP, confluence's title field IS redacted — but the adversarial pass surfaced **two
lone-unguarded-field parse gaps** and **two PII-in-a-field-framed-as-safe leaks** (mod-input boundary). With this
pass, **all 26 connectors are purple-team-validated.**

| Connector | Finding | Sev | Boundary |
|---|---|---|---|
| anthropic_admin | `starting_at` un-coerced (truthy non-str crashes) | low | mod-input/availability |
| openai_admin | out-of-range `effective_at` → `gmtime` OverflowError aborts the batch | medium | availability |
| continue_dev | free-form `modelTitle` reaches mod-input un-redacted | low | mod-input |
| confluence | page-title PII survives in `source_ref.url` (webui slug) | medium | mod-input |

## Findings (blue-verified + boundary-checked, file:line)

1. **ANTHROPIC-ADMIN-PARSE-1 — parse_robustness (low)** — `connectors/anthropic_admin/connector.py:57`
   `start = (bucket.get("starting_at") or "").strip()` floors only *falsy*; a **truthy non-str** `starting_at`
   (e.g. `123`) → `123.strip()` `AttributeError` at the connector's own boundary (the lone unguarded field; every
   token metric is `_int`-guarded). The runtime `_PARSE_SKIP` net catches it downstream, but the connector's
   documented "skip, don't crash (#59)" invariant should hold at its own boundary. **Fix:** isinstance-guard
   (`raw = bucket.get("starting_at"); start = raw.strip() if isinstance(raw, str) else ""`). **Sweep the sibling**
   `openai_admin/connector.py:46` (`(event.get("type") or "").strip()` — identical class) per SG-2026-06-12-B.
2. **OPENAI-ADMIN-PARSE-1 — parse_robustness (medium)** — `connectors/openai_admin/connector.py:26-30`
   `_event_time` guards `isinstance(effective_at, int)` but an **out-of-range int** (e.g. `10**20`) passes the
   isinstance check and `time.gmtime(10**20)` raises **OverflowError/OSError**, uncaught — aborting the whole poll
   batch (one bad row drops all). **Fix:** wrap `gmtime`/`strftime` in `try/except (OverflowError, OSError,
   ValueError)` returning `""` (matching the bad-type path); add `OverflowError`/`OSError` to
   `runtime/delivery._PARSE_SKIP` as a systemic per-row backstop.
3. **CONTINUE-PII-1 — pii_on_wire (low; mod-input)** — `connectors/continue_dev/connector.py:62-66`
   `metadata.model = str(event.get("modelTitle") or …)` is a **user-defined free-form string** (a developer names
   their model config); framing it as uniform "technical metadata" understates the PII surface. Metadata reaches
   the **mod-input** boundary (not the v1 wire — SG-2026-06-13-C), but it should still be redact-and-passed like
   the other free-text. **Fix:** `redact()` the model value (mirroring the `userId` author fix); correct the
   config.json/docs wording so `model` is not grouped with `name`/`schema` as uniform-technical.
4. **CONF-PII-URL-01 — pii_on_wire (medium; mod-input)** — `connectors/confluence/connector.py:62-67`
   `url=_page_url(content)` is emitted **un-redacted**, and the Confluence `_links.webui` carries the **page title
   as a URL slug** (`/spaces/X/pages/123/Onboarding+for+jane.doe…`). So page-title PII survives in `source_ref.url`
   even though the title *field* is redacted — and the config.json/references.md "jira/github redact parity" claim
   is therefore false for the url. The wire `source` redacts the url (`gateway_mapping._source`), but mods receive
   `source_ref.url` raw (mod-input). **Fix:** `url=redact(_page_url(content))` (and note URL-encoded PII in the
   slug, e.g. `%40`, as a disclosed residual — the title *field* is the canonical redacted surface); correct the
   config.json/references.md parity wording.

## Recommendations (one governed remediation cycle after this brief; modular-commit → PR → merge-if-green)

1. **PT-final4 (all 4 findings + the sibling sweep):** (a) isinstance-guard `starting_at` (anthropic_admin) AND
   `type` (openai_admin sibling sweep, SG-2026-06-12-B); (b) `try/except` the `gmtime` overflow + extend
   `runtime/delivery._PARSE_SKIP` with `OverflowError`/`OSError`; (c) `redact()` the continue_dev `modelTitle`
   metadata + correct its wording; (d) `redact()` the confluence `_page_url` + correct the parity wording. MEASURE
   (full suite green; the `_PARSE_SKIP` change is shared-core — SG-2026-06-05-F). Regression tests per finding.

## Updated Knowledge (Shadow Genome)

- **SG-2026-06-14-C** — *`isinstance(x, int)` is not enough before `time.gmtime`/`strftime`; an out-of-range int
  passes the type check and raises OverflowError/OSError.* `_event_time` (openai_admin) type-guarded but a huge
  `effective_at` crashed the batch. **Rule:** any `gmtime`/`localtime`/`strftime`/`fromtimestamp` on
  provider-supplied epoch ints must be wrapped in `try/except (OverflowError, OSError, ValueError)`; add those to
  the runtime per-row `_PARSE_SKIP` backstop too. (Pairs with the `(x or "").strip()` truthy-non-str class —
  fathom #164 / gitlab GITLAB-001 — both are "the lone field the per-leaf guards missed".)
- (Reinforces **SG-2026-06-13-C**: a field framed as "technical metadata" or a "provenance URL" still reaches the
  mod-input boundary — redact free-text-derived values (modelTitle, a title-bearing url slug) even when they don't
  reach the v1 gateway wire.)

---

_Recon complete. All four cleared with low/medium fixes (two parse-robustness, two mod-input PII); zero blocked.
This completes 26/26 connectors purple-team-validated. EM-safe + read-only + ADR-0012 + the headline claims
(PII-free aggregate / identity-dropped / redact-and-pass) all hold after remediation._
