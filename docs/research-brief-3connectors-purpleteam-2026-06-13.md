# Research Brief — local_directory + aider + zendesk purple-team

**Date**: 2026-06-13
**Analyst**: The Qor-logic Analyst (purple-team workflow `wf_b97afadb`, 7 agents: red penetration-tester → blue security-auditor → per-target verdict)
**Target**: the three newly-flip-ready connectors (local_directory #166, aider #167, zendesk #168) — the deferred adversarial pass.
**Method**: per connector, a red agent attacked across its attack classes (parse_robustness, pii_on_wire, identity_minimization, path_traversal/symlink for local_directory, webhook_replay/signature for zendesk, descriptor_accuracy, em_safe_contract); each finding was blue-verified against source, then the analyst re-verified IMPACT against the real gateway serializer.

---

## Executive Summary

**All three connectors = approved-with-fixes; ZERO blocked.** 4 findings confirmed (local_directory 2, aider 1,
zendesk 1), **all medium/low, none high**. The cores held: the Zendesk Base64-HMAC verify is sound, the
redact-and-pass + name-drop + opaque-token controls work, the webhook dedup is intact, all three are read-only
(no `em_safe_contract` breach), and local_directory's path is genuinely sha256-tokenized (no traversal/symlink
or layout leak). The four findings share **one root** and one **measured-down impact correction**.

### One root: a payload-derived field bypasses the redaction *and* the screen

| Field | Connector | Bypasses | Finding |
|---|---|---|---|
| `source_ref.kind` (from `source_type_label`) | local_directory | `redact()` **and** FX-SEC-001 | ld-1 (med→**low/med**), ld-2 (low) |
| `author` (from `author_name`) | aider | `redact()` (FX-SEC-001 *does* screen it) | aider-1 (med→**low**) |
| `author` (from `requester_id`) | zendesk | `redact()` (FX-SEC-001 *does* screen it) | zd-1 (med→**low**) |

`source_ref.kind` is the **only `SourceRef` sibling not in `_screen_sensitive`** (pipeline.py:133-136 scans
`url`/`ref`/`source_id` but not `kind`), even though its docstring claims it "covers EVERY wire-bound field."
The `author` field IS screened by FX-SEC-001 (line 136), so a secret/PHI/PAN in it is already hard-rejected;
the residual is only the email/phone class, which `redact()` would scrub but the connectors never apply to the
identity field.

### The impact correction (verify-before-fix; new SG-2026-06-13-C)

The red agents asserted these fields "reach the wire." **They do not reach the v1 gateway wire.** The actual
serializer `runtime/gateway_mapping.py:emission_to_ingest_request` (lines 56-62) maps an emission to the v1
`IngestRequest` using **only** `title` / `description` / `source` (redacted url-or-ref) / `source_type`
(source_id) / `evidence[].excerpt`. It **drops `kind`, `author`, `timestamp`, and metadata entirely.** So the
confirmed gaps are NOT live gateway-wire leaks. They are real at two narrower boundaries:

1. **Mod-input boundary** — mods consume the *full* in-process `AdapterEmission` (including `kind`/`author`/
   metadata), and `run_mod` reuses `validate_emissions`/`_screen_sensitive`. This is exactly why `author`/
   `timestamp`/`metadata` are already screened despite not being in the v1 wire. `kind` is the lone gap.
2. **Descriptor honesty + defense-in-depth** — the config.json/references.md claims ("un-bypassable backstop",
   "never a name/email", "no contact handle leaks") are stated as absolutes the code does not yet enforce; and
   `kind` is the one `SourceRef` field a future sink mapping could serialize without a screen behind it.

The fixes are therefore warranted (mod-boundary parity + honest descriptors + defense-in-depth), at the
corrected severities above — not as wire-leak emergencies.

## Findings (blue-verified + impact-corrected, file:line)

### local_directory
1. **ld-1 — pii_on_wire (low/med)** — `connectors/local_directory/connector.py:47` `source_type_label` flows
   into `SourceRef.kind` with no `redact()` and no FX-SEC-001 screen (`kind` absent from pipeline.py:135-136).
   An operator-supplied label carrying a secret/email reaches the **mod-input** boundary un-checked. Fix
   (two layers): **platform** — add `ev.source_ref.kind` to the `_screen_sensitive` scan list (closes it
   fleet-wide for secret/PHI/PAN at the mod boundary, and corrects the "EVERY wire-bound field" docstring);
   **connector** — `kind = redact(str(payload.get("source_type_label") or _DEFAULT_KIND))` (the email/phone
   class, for the one connector taking a freeform operator label).
2. **ld-2 — descriptor_accuracy (low)** — `connectors/local_directory/config.json` pii_posture calls FX-SEC-001
   the "un-bypassable backstop" while `kind` sat outside the screened surface. **Auto-resolves** once ld-1's
   platform fix lands (the screen then genuinely covers `kind`).

### aider
3. **aider-1 — pii_on_wire / descriptor honesty (low)** — `connectors/aider/connector.py` retains
   `author=str(record.get("author_name") or "")`. FX-SEC-001 already screens `author` for secret/PHI/PAN; the
   residual is an **email/phone-shaped** `author_name` (e.g. a CI bot `git user.name = "deploy-bot@corp.com"`),
   which `redact()` is not applied to — contradicting the descriptor's "no contact handle leaks." Fix:
   `author=redact(str(record.get("author_name") or ""))` — a real name has no email/phone shape and survives
   untouched (honors SG-2026-06-13-B name-retention), while an email/phone-shaped name is scrubbed. The
   `(aider)` attribution token is preserved.

### zendesk
4. **zd-1 — pii_on_wire / descriptor honesty (low)** — `connectors/zendesk/connector.py:83`
   `author=_text(detail.get("requester_id"))` is emitted without `redact()`; the descriptor promises requester
   is "an opaque id, never a name/email." A numeric id is opaque, but the guarantee is *trusted, not enforced* —
   a stray email/phone in `requester_id` would pass. Fix: `author=redact(_text(detail.get("requester_id")))` —
   a numeric id passes byte-for-byte unchanged (opaque-id contract preserved), an email/phone is scrubbed.

## Recommendations (2 governed remediation cycles after this brief; each modular-commit → PR → merge-if-green)

1. **PT-A — kind screen + local_directory label (platform + connector):** add `ev.source_ref.kind` to
   `_screen_sensitive` and update its docstring; `redact()` the local_directory `source_type_label`. Regression
   tests: a secret in `source_ref.kind` raises `EmissionContractError`; an email in `source_type_label` is
   scrubbed.
2. **PT-B — identity-field redact (aider + zendesk):** `redact()` the aider `author_name` and the zendesk
   `requester_id`; tighten the two descriptors' wording to "redact-and-passed (email/phone scrubbed)". Regression
   tests: email-shaped author scrubbed but a real name + `(aider)` preserved; email-shaped requester_id scrubbed
   but a numeric id unchanged.

(jira/linear also derive `kind` from provider event-type tokens — the PT-A platform screen backstops them for
secret/PHI/PAN; their kinds are constrained enums, so no per-connector `redact()` is warranted there.)

## Updated Knowledge (Shadow Genome)

- **SG-2026-06-13-C** — *verify a finding's IMPACT against the real serializer, not the struct field's
  existence.* The red agents confirmed a true code gap (`kind`/`author` bypass `redact()`/the screen) but
  asserted it "reaches the wire" — yet `runtime/gateway_mapping.py:emission_to_ingest_request` drops
  `kind`/`author`/`timestamp`/metadata from the v1 `IngestRequest` entirely. The gap is real at the *mod-input*
  boundary and as descriptor-honesty/defense-in-depth, not as a gateway-wire leak. Always trace a "reaches the
  wire" claim to the actual emit/serialize function before assigning severity (cf. SG-2026-06-12-C: re-verify
  against the REAL envelope). The fix stands; the severity is measured down from medium to low.

---

_Recon complete. All three connectors cleared with low/medium fixes only; remediation in 2 governed cycles
(PT-A kind/label, PT-B identity redact). EM-safe + read-only boundary + ADR-0012 + the sound webhook/HMAC core
all hold._
