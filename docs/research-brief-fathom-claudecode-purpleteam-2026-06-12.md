# Research Brief — fathom + claude_code purple-team

**Date**: 2026-06-12
**Analyst**: The Qor-logic Analyst (purple-team workflow `wo48b3pak`, 10 agents)
**Target**: the two newly-flip-ready connectors (fathom #160, claude_code #161) — the deferred adversarial pass.
**Method**: 6 attack classes (parse_robustness, pii_on_wire, identity_minimization, webhook_replay_signature, descriptor_accuracy, em_safe_contract) red-attacked per connector, each finding blue-verified against source.

---

## Executive Summary

**Both connectors = approved-with-fixes; ZERO blocked.** 7 findings confirmed (fathom 3, claude_code 4), **3 medium + 4 low, none high**. The cores held: the Svix webhook verify is sound (constant-time HMAC, base64, fail-closed, 5-min window), the redact-and-pass + name-drop + cwd-scrub controls work for the common cases, FX-SEC-001 is intact, both are read-only (no `em_safe_contract` breach). The defects are edge robustness, redaction completeness, and a path-layout gap — three roots:

| Root | Findings | Fix |
|---|---|---|
| **phone-redaction completeness** (shared) | fathom pii (low) + claude_code pii (med) | `_PHONE_RE` requires a literal `+` for international; non-`+` (`00`-prefix, bare national grouping) bypasses. Broaden + correct the over-claiming docstring/descriptors. **adapter/core/redaction.py** → all redact-and-pass connectors |
| **fathom parse-robustness** | fathom parse (med) + (low) | `default_summary` truthy non-dict (`(x or {}).get` floors only falsy) raises `AttributeError` at connector.py:63; `normalize_event` parses a non-dict JSON body (it lacks the `isinstance(payload, dict)` guard `observations()` has). |
| **claude_code identity + floor** | claude_code id (med) + floor (low) + descriptor (low) | `_HOME_RE` misses UNC (`\\server\Users\<u>`), WSL (`\\wsl$\<d>\home\<u>`), `/export/home/<u>` → cwd username leaks; the floor literal's raw uuid can carry an email-shaped value (un-redacted); config.json over-claims "username never reaches the wire". |

## Findings (blue-verified, file:line)

### Fathom
1. **parse_robustness (medium)** — `connectors/fathom/connector.py:63` `summary = _s((meeting.get("default_summary") or {}).get("markdown_formatted"))`: a truthy non-dict `default_summary` (provider drift / a validly-signed payload) → `"done".get(...)` `AttributeError` before `_s`. `or {}` floors only None/falsy. No backstop (parse raises before `normalize`). Fix: `ds = meeting.get("default_summary"); summary = _s(ds.get("markdown_formatted")) if isinstance(ds, dict) else ""`.
2. **parse_robustness (low)** — `connectors/fathom/connector.py:132-136` `normalize_event` wraps only `json.loads`; a signed body that decodes to a list/scalar (`[1,2,3]`) reaches `parse_meeting` → `meeting.get` `AttributeError`. `observations()` guards with `isinstance(payload, dict)`; `normalize_event` doesn't (asymmetry). Fix: add the dict-guard (or route the webhook path through `self.observations`). Reachable only by the Svix-secret holder (signed) — provider drift, not external forgery.
3. **pii_on_wire (low)** — `adapter/core/redaction.py:30-36` `_PHONE_RE` is NANP-3-3-4 + `+`-prefixed-E.164 only; `0049 30 1234 5678` / `020 7946 0958` / `06 12 34 56 78` bypass and reach the transcript/summary/title emission. Loose PII (no name — speaker/recorder names dropped), non-Live, private advisory stream.

### Claude Code
4. **identity_minimization (medium)** — `connectors/claude_code/connector.py:35` `_HOME_RE` anchors only drive-letter / `/Users/` / `/home/`. A UNC cwd `\\fileserver\Users\bob.jones\proj` (also WSL `\\wsl$\Ubuntu\home\<u>`, Solaris/NFS `/export/home/<u>`) matches none → `_safe_cwd` returns it verbatim → the OS username reaches metadata/wire (FX-SEC-001 does not catch a username). Fix: extend `_HOME_RE` to UNC/WSL/export-home (or emit only the project basename).
5. **pii_on_wire (medium)** — same `_PHONE_RE` gap, on the excerpt content; the descriptor/docstring over-claim "email/phone scrubbed" (true only with `+CC`).
6. **pii_on_wire (low)** — `connectors/claude_code/connector.py:93` the floor literal `[claude_code:kind] <uuid>` is un-redacted (by design, to avoid mis-scrubbing the uuid's digit groups as a phone); a poisoned uuid containing an email (`contact-jane@corp.com-id`) leaks — FX-SEC-001 catches secret/PHI/PAN, not email. Fix: sanitize the ref to the opaque-id shape (`[A-Za-z0-9_-]{1,64}`) before the floor (elide otherwise); apply to `source_ref.ref` too.
7. **descriptor_accuracy (low)** — `connectors/claude_code/config.json:13` the absolute "OS username never reaches the wire" is contradicted by the UNC gap. Fix: scope the claim to the covered families (and restore once the regex covers UNC/WSL).

## Recommendations (2 governed fix cycles after this brief; each modular-commit → PR → merge-if-green)

1. **PT1 — phone-redaction completeness (shared):** broaden `_PHONE_RE` with a `00` international prefix (alongside `+`) + a context-anchored national branch (require a `tel/phone/call/…` token, no over-redaction of bare ids), keep O(n), re-assert `detect_sensitive(redact(x)) == []`, add a corpus test, and correct the docstring + `DATA_CLASSIFICATION_AND_REDACTION.md` to state exact coverage.
2. **PT2 — fathom + claude_code connector fixes:** fathom `default_summary` isinstance guard + `normalize_event` dict-guard; claude_code `_HOME_RE` UNC/WSL/export-home + `_safe_ref` floor/ref sanitize + scope the descriptor claim. Regression test per finding.

## Updated Knowledge (Shadow Genome)

- **SG-2026-06-12-I** — *a phone-redaction broadening that requires a literal `+` still misses non-`+` international.* The deep-audit E.164 branch (#150) covered `+CC` but not the `00` international-dialing prefix or bare national groupings — and the docstring then over-claimed "UK/FR/DE/CN/AU/IN." Pair every redaction-coverage broadening with an adversarial corpus AND a docstring that states the EXACT covered shapes.
- **SG-2026-06-12-J** — *a home-prefix scrub must enumerate EVERY home layout (UNC / WSL / network share / export-home), not just `C:\Users` + `/Users` + `/home`.* A path-based identity scrub anchored to local roots leaks the username on network/UNC/WSL paths; prefer the most robust form (e.g. emit only the basename) or scope the guarantee honestly.

---

_Recon complete. Both connectors cleared with low/medium fixes only; remediation in 2 governed cycles (PT1 shared redaction, PT2 connector fixes). EM-safe + read-only boundary + ADR-0012 hold._
