# Research Brief — design + prioritize the 9 scaffolded mods

**Date**: 2026-06-12
**Analyst**: The Qor-logic Analyst
**Target**: the 9 scaffolded mods (manifest + README + references + fixtures, no `connector.py` impl) — turn each into a working EM-safe advisory mod and wire it into `runtime/runner_registry._MODS`.
**Pattern authority**: `mods/dependency_risk/connector.py` (the reference EM-safe mod) + `mods/contract.py` (`run_mod`, `ModEmission`, `_KNOWN_OUTPUTS`).

---

## Executive Summary

Four mods are complete and wired (`dependency_risk`, `data_classification`, `noisy_source_gate`, `security_mentions`); **9 are scaffolds**. Each scaffold already declares its `manifest.yaml` (`id`/`version`/`outputs`/`forbidden_actions` ⊇ the EM-safe baseline) and a README scope. What is missing is the `connector.py` — the `Mod` class with a pure, deterministic, stdlib-only `evaluate(emissions) -> list[ModEmission]`.

**Key constraint (governs every design below):** a mod is a **pure function over `AdapterEmission` objects** — it has NO filesystem/repo/network access (`run_mod` re-screens input, validates outputs, and the mods are I/O-free by contract). So every detector keys off what the emission actually carries: `source_id`, `title`, `body`, each `evidence[].source_ref` (`source_id`/`ref`/`url`/`kind`), `excerpt`, `author`, `timestamp`, and connector `metadata` (preserved through `normalize`, ADR-0014). This is exactly how `dependency_risk` works (vuln-kind evidence + metadata; manifest-filename substrings in text). The honest-confidence discipline carries over: **route only on a strong signal; otherwise annotate** — and never fabricate a numeric score (no metadata key containing `confidence`/`score`/`probability`/`likelihood`; `AdvisoryResult` has no scalar-score field by design).

## Per-mod detection design (all deterministic, stdlib-only)

| Mod | Primary signal (over the emission) | Outputs | Route when |
|---|---|---|---|
| **adapter_contract** | the emission's OWN structure: empty/blank `source_ref.ref`, empty `url` on a URL-addressable kind, empty `timestamp`/`author`, zero `evidence`, or a `source_ref.kind` outside the known vocab | annotation + advisory + routing | a load-bearing ref/evidence pointer is missing (review the connector) |
| **source_trust_calibration** | provenance: `source_ref.kind` + `source_id`, missing `author` (no actor identity), unknown/blank `kind`, advisory `emission_type` | annotation + advisory + routing | weak provenance on a normally-attributable source (keep advisory / manual review) |
| **webhook_risk** | webhook-context evidence (`kind` in webhook event set, or text mentioning `webhook`/`signature`/`replay`/`idempotency`) lacking dedup/verify markers | annotation + advisory + routing | a webhook-triggered change touches verify/replay (route security) |
| **connector_freshness** | text mentions provider-API-version / `deprecat*` / `sunset` / `breaking change` / `v1→v2` migration terms, or `references.md`/`auth.md` staleness phrases | annotation + advisory + routing | a deprecation/version-break is named (route connector review) |
| **code_review_risk** | PR/change text references risky paths: `migration`/`schema`, `auth`/`login`/`token`, `.github/workflows`, `Dockerfile`, security paths, `breaking` | annotation + advisory + routing + review-question | a high-blast-radius area is named (route review) |
| **authority_boundary** | text references canonical-write/authority terms: `approve`/`signoff`/`merge`/`deploy`/`delete`/`bypass`/`credential scope`/`shell`/`production` | annotation + advisory + routing + review-question | an authority-crossing action is named (route governance) |
| **test_adequacy** | a behavior/code-change emission whose text references `fix`/`feature`/`refactor`/`migration` but mentions NO test path/term (`test`/`spec`/`fixture`) | annotation + advisory + routing + review-question | a behavior change with no test signal (ask the gap question) |
| **ownership_routing** | path/domain hints in text → a reviewer lens (`security`/`connectors`/`governance`/`ci`/`docs`) | owner_lens_hint + annotation + routing | a clear domain owner is implied |
| **decision_drift** | text references `ADR`/`decision`/`trust tier`/`supersede`/`contradict`/`no longer matches` | annotation + advisory + routing + review-question | a decision-conflict phrase is named (ask the review question) |

Each mod floors to **no output** when no signal is present (silence is the default; a mod that fires on everything is noise). Metadata stays free of score-like keys; `evidence_ids` cite only non-user-controlled refs where available (the `dependency_risk` precedent — a PR/MR ref is user-controlled, so it is omitted from `evidence_ids`).

## Build sequence (4 governed cycles, each modular-commit → PR → merge-if-green)

1. **M1 — provenance & contract integrity:** `adapter_contract` + `source_trust_calibration`. Most mechanically grounded (operate on emission *structure*, not fuzzy text) — establishes the build rhythm.
2. **M2 — connector/source health:** `webhook_risk` + `connector_freshness`.
3. **M3 — PR change-review family A:** `code_review_risk` + `authority_boundary` + `test_adequacy`.
4. **M4 — PR change-review family B:** `ownership_routing` + `decision_drift`. Completes all 13 mods.

Each cycle: implement `connector.py` (pure `evaluate`), unit tests (invoke the mod through `run_mod`, assert the artifact + EM-safe rejection paths — functionality, not presence), wire into `_MODS` + the `runner_registry` import, seal a bare-hex ledger entry, PR (no comma in the conventional-title scope), merge-if-green.

## Boundary (binding on all 9)

EM-safe (ADR-0007/0008/0013): advisory only — never write a canonical decision, approve, resolve, block CI, or mutate evidence; `run_mod` enforces the outputs-allowlist + opaque-score reject + per-leaf FX-SEC-001 screen (hardened #150). Mods read immutable evidence; the operator runtime / Review Bot consumes the advisory artifacts. No I/O, no repo access — signals come only from the emission stream.

---

_Research complete. The 9 scaffolds are designed as deterministic emission-stream heuristics on the `dependency_risk` pattern; build proceeds in 4 cycles. Findings are advisory — implementation decisions remain with the Governor._
