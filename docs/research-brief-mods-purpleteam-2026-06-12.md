# Research Brief — purple-team review of the 9 new advisory mods

**Date**: 2026-06-12
**Analyst**: The Qor-logic Analyst (purple-team workflow `wy2vqr6t6`, 53 agents, ~1.27M tokens)
**Target**: the 9 mods built this session (adapter_contract, source_trust_calibration, webhook_risk, connector_freshness, code_review_risk, authority_boundary, test_adequacy, ownership_routing, decision_drift) — held to the same red-attack → blue-verify bar as the connector deep-audit.
**Method**: 6 attack classes (crash_dos, em_safe_escape, pii_secret_output, false_positive_substring, false_negative, manifest_determinism) red-attacked per mod, **each finding adversarially blue-verified against source** before a per-mod verdict.

---

## Executive Summary

**All 9 mods = approved-with-fixes; ZERO blocked.** 40 findings confirmed real (of ~44 raised), **36 low + 4 medium, none high/critical**. The EM-safe cores held exactly as designed: no `em_safe_escape` (the `run_mod` chokepoint — outputs-allowlist + opaque-score reject + per-leaf FX-SEC-001 screen + input re-screen — was not bypassed), no Live consumer, no canonical-write/route-escalation that crosses a real trust boundary. The defects are **edge robustness, precision, and recall** in advisory-only, non-Live code.

The 40 cluster into **4 fix families**:

| Class | Count | Root | Fix |
|---|---|---|---|
| **crash_dos** | 14 | a hand-built malformed emission (non-str `source_id`, None/dict `source_ref`, None evidence, unhashable `kind`) raises a raw `TypeError`/`AttributeError` instead of the contract's fail-closed `EmissionContractError`. The production `run_mod` path fail-closes FIRST via `validate_emissions`, so reachable only by a direct `evaluate()` call (the mods' own tests) — but the boundary should be uniformly typed. | **shared**: `adapter/core/pipeline.py` `validate_emissions`/`_screen_sensitive` type-guards (covers all mods + normalize) + per-mod `evaluate`-totality guards |
| **false_positive_substring** | 12 | bare `t in text` substring matching: `auth`∈"author", `adr`∈"quadratic/cadre", `retire`∈"retired/tired", `policy`∈"policyholder", `crypto`∈"cryptocurrency", `overrides`/`reverses`/`out of date` in ordinary technical prose. Fires a spurious ROUTE (worse than annotate). | **word-boundary token matching** (shared helper; keep substring for path/phrase terms like `.github/workflows`, `docs/`, `parse surface`) |
| **false_negative** | 12 | fixed keyword lists miss real phrasings: security CVE/XSS/CSRF/RCE/SQLi, deprecation decommission/discontinue/EOL, authority synonyms, decision obsolete/rescinded/revoked, test verbs patch/rewrite, and attributable kinds the connectors actually emit (commit/merge_request/ticket/document/transcript/session/incident/finding; `comment` is a dead allowlist entry). | **vocab expansion**, folded into the word-boundary cycle (safe once boundaries are in) |
| **pii_secret_output** | 2 | a mod echoes a raw `source_id` into its message/metadata; the FX-SEC-001 screen catches secret/PHI/PAN but NOT a generic name/email. `adapter_contract` echoes the **evidence-level** `source_ref.source_id` (never input-validated); `decision_drift` echoes `emission.source_id` (input-validated to `^[A-Za-z0-9._-]+$`, so only a conforming-but-PII id like `john.doe` slips). | **sanitize `source_id`** against the conforming pattern before echoing |

## Notable per-mod specifics (the 4 mediums)

- **connector_freshness (med):** `retire`∈"retired/retirement/tired" → spurious connectors route.
- **code_review_risk (med)** + **test_adequacy (med):** an **unhashable** `source_ref.kind` (a list/dict) crashes `_is_change` at the `kind in _CHANGE_KINDS` frozenset-membership test (`TypeError: unhashable type`) — direct-call path; the chokepoint type-guard + a per-mod guard close it.
- **test_adequacy (med, correctness):** `test`∈"latest/contest/testbed" → `_TEST_TERMS` falsely concludes "tests already referenced" and **suppresses a real test-gap signal** (false negative). Word-boundary matching fixes it.

## Blueprint alignment

| Claim | Finding | Status |
|---|---|---|
| Mods are pure TOTAL functions over `AdapterEmission` | `evaluate()` raises on malformed emission shapes (direct-call path) | DRIFT → MP1 + MP2 totality guards |
| `run_mod` input boundary is uniformly fail-closed (`EmissionContractError`) | `validate_emissions` leaks raw `TypeError`/`AttributeError` on type-malformed fields | DRIFT → MP1 |
| Keyword detection fires on the intended terms only | bare substring matching over-fires on innocent words | DRIFT → MP2 |
| Mods emit only their own constants + a screened id | a raw/evidence-level `source_id` is echoed past the screen | DRIFT → MP2 leak-safety |

## Remediation (2 governed fix cycles after this brief; each modular-commit → PR → merge-if-green)

1. **MP1 — shared chokepoint type-guards** (`adapter/core/pipeline.py`): `validate_emissions` + `_screen_sensitive` raise `EmissionContractError` on non-str `source_id`/`emission_type`, None/non-`SourceRef` `source_ref`, non-iterable evidence, non-str `author`/`excerpt`/`timestamp`/`ref`/`url`. Converts the whole crash_dos class to fail-closed at one place — all 9 mods + normalize + the `run_mod` input boundary.
2. **MP2 — mod precision + totality + leak-safety** (the 9 mod connectors + a shared `mods/_text_match.py` token matcher): word-boundary matching (false_positive_substring) + vocab expansion (false_negative) + per-mod `evaluate`-totality guards (`evidence or ()`, unhashable-`kind` guard, `source_id` `.strip()` guard) + `source_id` sanitization (pii_secret_output) + source_trust attributable-kind catalog. Regression test per finding.

## Updated Knowledge (Shadow Genome)

- **SG-2026-06-12-E** — *a keyword/substring heuristic over free text MUST word-boundary-match alphabetic terms.* Bare `term in text` over-fires on superstrings (`auth`∈author, `adr`∈quadratic, `retire`∈retired) — a precision defect that erodes trust in an advisory stream. Tokenize on non-alphanumerics and match whole tokens; reserve substring for genuine path/phrase terms.
- **SG-2026-06-12-F** — *a "pure total function" contract must be enforced at the SHARED input boundary, not assumed.* The mods' `evaluate` and `validate_emissions` both leaked raw `TypeError`/`AttributeError` on type-malformed (vs merely empty) emission fields. Type-guard at the chokepoint so every consumer is uniformly fail-closed (extends SG-2026-06-12-B).

---

_Recon complete. All 9 mods cleared with low/medium fixes only; remediation in 2 governed cycles (MP1 chokepoint, MP2 mod hardening). Findings advisory — remediation decisions remain with the Governor; EM-safe boundary + ADR-0013 hold._
