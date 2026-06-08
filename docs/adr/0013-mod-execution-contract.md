# ADR-0013: Mod Execution Contract

**Date:** 2026-06-08
**Status:** Accepted
**Level:** L1
**Extends:** ADR-0002 (EM-Safe Mod Manifest), ADR-0007 (EM-Safe Mod Boundary), ADR-0008 (evidence-not-authority)

## Context

13 EM-safe mods are scoped (README + `references.md` + `manifest.yaml`) but nothing *executes*
them — there is no `Mod` interface and no runner. ADR-0002/0007 define the *declarative* contract
(manifest + forbidden actions); this ADR adds the **runtime** contract so every mod runs through one
manifest-enforced, EM-safe chokepoint. Runtime stays **stdlib-only**.

## Decision

A mod is an **advisory post-processor** over adapter emissions. The execution contract lives in
`mods/contract.py` (+ the stdlib manifest reader in `mods/_manifest.py`):

- **`Mod`** protocol: `id` (canonical hyphenated, e.g. `dependency-risk`), `version`, `outputs:
  frozenset[str]`, `evaluate(emissions: list[AdapterEmission]) -> list[ModEmission]`.
- **`ModEmission`** (frozen): `output_type` + exactly one of `advisory: AdvisoryResult` /
  `routing_hint: RoutingHint`, with `__post_init__` binding the tag to the artifact (only
  `routing_hint` → `RoutingHint`; the other five kinds → `AdvisoryResult` whose `kind == output_type`).
- **`run_mod(mod, emissions, manifest)`**: validate the manifest⟷code contract, run `evaluate`, then
  enforce per artifact and **return the validated artifacts** — it writes nothing canonical.

### EM-safe enforcement (how each ADR-0007 prohibition is held)

| Forbidden action | Enforcement |
|---|---|
| write canonical decision / approve signoff / resolve compliance / create blocking result | **by construction** — a mod's only output channel is *returning* advisory artifacts; no such method exists |
| delete / mutate source evidence | **by construction** — `AdapterEmission`/`SourceEvidence` are frozen dataclasses (mutation raises) |
| bypass governance policy | **by construction** — a mod has no policy handle to bypass; also declared in every manifest's `forbidden_actions` |
| collapse confidence into one opaque score | **by construction + runtime guard** — `AdvisoryResult` has no first-class scalar score field, so a dimensional `ConfidenceSurface` is the only confidence channel; `run_mod` additionally rejects a numeric metadata value under a score-like key (`confidence`/`score`/`probability`/`likelihood` substring), walked into nested metadata, to catch score-smuggling. The guard is a defence-in-depth lint over key *names*, not a proof that no number exists — the structural absence of a score field is the actual guarantee |
| (allowlist) emit an undeclared output type | **runtime check** — every `ModEmission.output_type` must be in the mod's manifest-declared `outputs` |
| (integrity) surface a secret it detected | **runtime check** — `run_mod` runs the FX-SEC-001 `detect_sensitive` screen over every wire-bound artifact field and HARD-rejects a secret/PHI/PAN hit (the runner is the single chokepoint, mirroring `pipeline._screen_sensitive`) |

`validate_manifest` additionally requires `mod.id`/`version`/`outputs` to mirror the `manifest.yaml`
(the governance manifest is source of truth) and `manifest.forbidden_actions ⊇` the full EM-safe
baseline (`write_canonical_decision`, `approve_signoff`, `resolve_compliance`,
`create_blocking_ci_result`, `bypass_governance_policy`, `mutate_source_evidence`,
`collapse_confidence_score`) — all 13 manifests are normalized to declare this set.

### Manifest v1 schema (narrowing)

ADR-0002/0007 describe a fuller manifest (supported source types, confidence dimensions, audit
preservation). The **v1** manifest this contract loads is narrowed to
`id / version / name / outputs / forbidden_actions`; **source-types, confidence-dimensions, and
audit-preservation are deferred** to a future manifest-schema cycle. "The manifest is the source of
truth" is therefore scoped to the fields it actually declares. The loader parses a flat YAML subset
with a small stdlib reader (no PyYAML — preserves stdlib-only), fail-closed on nesting / tabs /
duplicate keys / unknown keys / empty `forbidden_actions`; scalars stay `str` (no float coercion);
CRLF + BOM tolerated.

## Consequences

- Every mod runs through one EM-safe, manifest-enforced, FX-SEC-001-screened chokepoint; mod authors
  write only `evaluate` + a code/manifest output declaration.
- No bot wiring here — feeding mod outputs to bot `preflight.run` is RFQ #42 territory.
- No third-party dependency; `mods/` enters the lint/type/test CI scope.
- First mod built on this contract: **dependency_risk** (next cycle).

## Alternatives considered

- **PyYAML for manifests** — rejected (breaks stdlib-only); a flat-subset stdlib reader suffices.
- **Enforce the boundary only at the bot** — rejected; the mod runner is the natural, testable
  chokepoint and keeps the EM-safe guarantee local + provable.
- **A scalar confidence on AdvisoryResult** — rejected (ADR-0007 forbids an opaque score;
  `ConfidenceSurface` is dimensional).
