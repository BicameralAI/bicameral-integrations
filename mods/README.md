# EM-Safe Mods

**Mods are advisory post-processors over adapter emissions.** They read the
evidence a connector produces and emit *hints* — risk signals, routing
suggestions, classification annotations — that help a reviewer act faster. They
**cannot** write canonical decisions, approve signoff, resolve compliance, or
create blocking results. That boundary is the **mod safety contract**, enforced
from the [project root](../README.md#mod-safety-contract) and grounded in
[ADR-0008](../docs/adr/0008-integrations-are-evidence-adapters-not-state-authorities.md):
integrations observe; they never own authority.

## What a mod produces

Mods emit only advisory artifacts — `source_evidence_annotation`,
`routing_hint`, `advisory_governance_result`, `owner_lens_hint`,
`suggested_review_question`, `dependency_signal`. A mod may surface a concern; it
may not act on it. Every mod output is reviewable, attributable, and non-blocking
by construction.

## How a mod runs (ADR-0013)

A mod implements the `Mod` protocol in [`contract.py`](contract.py) (`id` /
`version` / `outputs` + `evaluate(emissions) -> list[ModEmission]`) and is executed
through `run_mod`, the single EM-safe chokepoint:

- **evidence is immutable** (frozen `AdapterEmission`/`SourceEvidence`) and the only
  output channel is *returning* `ModEmission` artifacts — so writing canonical
  decisions, approving signoff, resolving compliance, blocking, or mutating evidence
  are not representable;
- `run_mod` enforces the rest at runtime: a mod may emit only its **manifest-declared
  `outputs`**; `id`/`version`/`outputs` must **mirror its `manifest.yaml`**; no opaque
  numeric confidence score (dimensional `ConfidenceSurface` only); and every wire-bound
  artifact field is run through the **FX-SEC-001** sensitive screen (a mod that *finds*
  a secret must not surface it). All fail-closed.

Manifests are loaded by the stdlib reader in [`_manifest.py`](_manifest.py) (no
PyYAML). See [ADR-0013](../docs/adr/0013-mod-execution-contract.md).

## Mods

| Mod | Advises on | Status |
|---|---|---|
| [dependency_risk](dependency_risk/) | Dependency upgrade, pin, SDK-drift, and compatibility-risk signals | Scoped |
| [noisy_source_gate](noisy_source_gate/) | Manual-gate high-noise sources (Slack, email, meetings) unless trust is configured higher | Scoped |
| [security_mentions](security_mentions/) | Auth, token, secret, PII, webhook-verification, and transport-exposure signals | Scoped |

## Planned suite

Additional mods are scoped and under active development on a dedicated track,
grouped by the concern they advise on:

- **Evidence integrity & adapter quality** — `adapter_contract` (evidence-shape /
  contract-preservation risks), `connector_freshness` (stale provider
  assumptions in docs/fixtures/auth/parser scope), `test_adequacy` (missing or
  weak tests around changed behavior).
- **Security & sensitivity** — `webhook_risk` (signature verification, replay,
  schema, idempotency, outbound side effects), `data_classification` (classify
  sensitive evidence before routing/notification).
- **Governance & authority** — `authority_boundary` (changes crossing
  authority/trust-tier/canonical-state boundaries), `decision_drift` (evidence
  conflicting with recorded decisions/ADRs/trust tiers), `source_trust_calibration`
  (trust from provenance, type, noise, sensitivity, operation tier).
- **Review routing & risk** — `code_review_risk` (PR-level review risk; the first
  family behind the [Review Bot direction](../docs/adr/0011-bicameral-review-bot.md)),
  `ownership_routing` (reviewer-lens / domain-ownership suggestions).

This index is documentation only; mod implementations are built and maintained
on a dedicated track.
