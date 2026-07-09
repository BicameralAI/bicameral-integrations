# ADR-0014: Emission metadata preservation through the normalizer

**Date:** 2026-06-08
**Status:** Accepted
**Level:** L2 (touches the FX-SEC-001 sensitive-data gate)
**Extends:** ADR-0004 (universal normalizer seam), ADR-0005 (neutral emission contract), ADR-0008 (evidence-not-authority)

## Context

Connectors yield `Observation` (`adapter/core/observations.py`); the single normalizer
`pipeline.normalize` → `_emission_from` turns each into an `AdapterEmission` consumed by mods (and,
in future, the bot gateway). Research (2026-06-08) found `_emission_from` **dropped
`Observation.metadata`** entirely — it copied only `source_ref`/`excerpt`/`author`/`timestamp` and
`source_id`/`title`/`body`. No test guarded the behaviour either way.

Consequence: structured signals a connector computes — the **OSV** connector's
`metadata={"severity","packages","aliases"}`, ServiceNow's `number/state/priority`, etc. — never
reach a mod. Every mod was silently limited to free text. This blocks `dependency_risk` (the reference
mod) and the whole planned mod suite from using structured provider data.

## Decision

1. **Preserve metadata.** `_emission_from` carries `dict(obs.metadata)` (defensive copy) into
   `AdapterEmission.metadata`. Emission-level: one Observation → one emission; mods read
   `emission.metadata`.

2. **Metadata is a screened wire-bound surface, scanned PER LEAF.** Because metadata now flows to an
   in-process consumer (mods), it must pass the FX-SEC-001 `detect_sensitive` screen. `_screen_sensitive`
   gains a `_metadata_strings` flatten that yields **every string leaf and every dict key**, recursing
   dicts (keys+values), lists/tuples/sets, and stringifying non-str scalars. Each leaf is scanned by its
   **own** `detect_sensitive` call — **not** appended to the existing space-joined core blob.
   - *Why per-leaf:* PAN detection suppresses a candidate preceded within 30 chars by an id-label
     (`sensitive._is_id_preceded`). A single join would let `{"note":"…order_id:", "card":"<PAN>"}`
     become `"…order_id: <PAN>"` and **suppress a real PAN — a false negative**. Per-leaf cannot
     fabricate cross-leaf adjacency, while still honouring legitimate within-leaf id-label suppression.

3. **Close the activated `run_mod` input boundary.** Dropping metadata had masked a latent gap:
   `run_mod` consumes raw `AdapterEmission` and screened only mod *output* (`_wire_text`), never input.
   Preserving metadata makes a hand-built secret-bearing emission handed straight to `run_mod` an
   exposure. `run_mod` now calls `validate_emissions(emissions)` first — a defensive input re-screen
   mirroring `GatewaySink.emit`. Layering is legal (mods → adapter); no import cycle (`pipeline` does
   not import `mods`).

### Relationship to ADR-0005 (neutral contract)

ADR-0005's stance — *evidence carries only an excerpt; the gateway/daemon owns judgment; the wire
envelope stays minimal* — is preserved. Metadata is kept **in-process for mods only**; it is **not**
wire-forwarded (`runtime/gateway_mapping.emission_to_external_envelope (nee emission_to_ingest_request; #226)` builds title/description/source/
evidence and does not include metadata, and `GatewaySink.emit` re-screens at its own boundary). So the
minimal-wire contract is unchanged; metadata is screened because mods are an in-process consumer, not
because it reaches the wire.

## Consequences

- Mods can read structured connector signals (`emission.metadata`); `dependency_risk` can use OSV's
  `packages`/`severity` rather than re-parsing free text.
- The FX-SEC-001 screened surface widens to metadata (keys + nested values + container items +
  stringified scalars) — strictly more is screened, fail-closed direction; no field is removed.
- `run_mod` is now a fail-closed input boundary as well as an output boundary.
- `_metadata_strings` (pipeline) and `_flatten_strings` (mods/contract) are intentionally-duplicated
  nested-flatteners (adapter must not import mods); change both together.

## Residual risks (for the ledger)

1. **Exotic metadata types** outside `{dict, list, tuple, set, str, scalar-with-__str__}` — custom
   `Mapping`/`Iterable` subclasses, generators, decoded `bytes` content — are stringified at best, not
   deep-walked. A **self-referential** container would `RecursionError` (fails closed — rejects, not a
   bypass). Both are out of the realistic surface (`metadata` is `dict[str, Any]` from stdlib-parsed
   connector JSON, which cannot cycle); same residual as `_flatten_strings`.
2. **Duplication** between `pipeline._metadata_strings` and `mods.contract._flatten_strings` — now
   behaviourally identical (both walk keys+values+containers; pre-seal review aligned `_flatten_strings`
   to also screen dict keys, closing the mod-output-metadata-key gap). Still no shared parity test; the
   docstrings flag "change both together."

## Alternatives considered

- **Single-join metadata screen** — rejected (fabricates `_is_id_preceded` PAN suppression →
  false negative; measured wrong during audit, SG-2026-06-05-F).
- **Shared flatten util in adapter imported by mods** — rejected for now (larger refactor; the
  duplication is small and flagged).
- **Screen metadata only at the gateway** — rejected; mods are an earlier in-process consumer, so the
  producer gate (`validate_emissions`) is the correct chokepoint, with `run_mod` as defence-in-depth.
