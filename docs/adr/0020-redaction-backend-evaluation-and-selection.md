# ADR-0020: Evaluate the redaction backend before selecting or replacing it

**Date:** 2026-07-23  
**Status:** Proposed (evaluation required; no backend selected)  
**Level:** L3 (sensitive-data boundary, production dependency, packaging, and cross-repository receipt implications)  
**Owner:** Kevin Knapp  
**Decision issue:** #277  
**Supporting issues:** #278, #279, #280  
**Advances:** #258, #260  
**Implementation baseline:** PR #269 at `fd69ff2742363b5d619bc073b8e8490c0f50733d`  
**Protocol dependency:** PR #262  
**Cross-repository architecture:** BicameralAI/bicameral-factory#280 and #281

## Context

Integrations requires one mandatory redaction boundary before screened provider evidence may be emitted to Bot. Redaction is a security and privacy hard gate, separate from fail-open relevance and noise advisories.

PR #269 establishes a reviewed Bicameral-owned wrapper and evidence boundary with:

- explicit admitted-field and structural-identity policy;
- deterministic replacement placeholders;
- value-free findings and receipts;
- deterministic input, output, and ruleset digests;
- process isolation;
- one monotonic deadline covering lock wait, worker creation, execution, response, and cleanup;
- bounded terminate and kill recovery;
- a hard-screen postcondition;
- no Bot-bound envelope and no cursor advancement on redaction failure;
- exact-head evidence generation.

The current detector is the repository-owned `bicameral-stdlib-redaction` engine, implemented through the sensitive-value catalog plus bounded custom detection for email and phone forms.

Presidio was discussed as a credible production-ready framework because it supports predefined and custom recognizers, local NLP engines, contextual detection, and separate analysis and anonymization components. That discussion did not establish Presidio as the best option. It was the only named alternative discussed in depth.

Selecting a detector from conversational availability would replace a reviewed security boundary without comparative evidence. The repository therefore needs a governed evaluation that can select Presidio, another candidate, or the current engine.

## Decision

Do not select or migrate the production redaction backend until a reproducible comparative evaluation is complete and Kevin records the owner decision in #280.

Preserve the Bicameral wrapper as the stable architecture boundary. Treat detector and anonymizer implementations as replaceable backends behind that wrapper.

```text
authenticated provider input
  -> Bicameral admitted-field and identity policy
  -> replaceable redaction backend
  -> Bicameral deterministic replacement policy
  -> existing hard-screen postcondition
  -> Bicameral value-free receipt
  -> universal normalization
  -> Bot-bound envelope
```

The wrapper remains authoritative for:

- which fields are admitted and sanitized;
- which identity fields must remain byte-for-byte stable;
- deterministic placeholder semantics;
- receipt schema and digest domains;
- timeout and worker lifecycle;
- value-free errors and diagnostics;
- structural-preservation assertions;
- post-redaction sensitive-data screening;
- failure and cursor behavior.

A backend may own only detection and backend-local analysis. It may not own provider identity, evidence identity, cursor state, receipt authority, Product state, candidates, Decisions, or downstream acceptance.

## Evaluation requirements

### Minimum candidates

The comparison must include at least:

1. the current Bicameral custom engine as the baseline;
2. Presidio with a pinned conventional local NLP configuration plus Bicameral custom recognizers;
3. Presidio with a credible pinned contextual PII recognizer such as GLiNER;
4. at least one credible lightweight local-first alternative when it passes the eligibility screen.

Hosted-only services may be documented as comparison references but are not eligible for the required alpha runtime.

A candidate may be rejected before implementation when primary-source research establishes an incompatible license, unsuitable maintenance posture, inability to operate offline, unpinnable provenance, unsupported packaging target, or another hard disqualifier. Rejections must be recorded rather than silently omitted.

### Shared corpus

Every implemented candidate must run against the same versioned corpus containing only synthetic or irreversibly sanitized records.

The corpus must cover:

- names, email addresses, phone numbers, physical addresses, dates of birth, government identifiers, financial identifiers, credentials, secrets, health-related identifiers, IP addresses, and account identifiers;
- nested metadata and mixed entity classes;
- GitHub webhook and polling shapes;
- Linear webhook and GraphQL shapes;
- local-directory and bounded-document-fetch shapes;
- `Observation`, `AdapterEmission`, and `ExternalIngestEnvelope` records;
- decision-bearing text containing sensitive values;
- negative controls containing commit SHAs, UUIDs, timestamps, URLs, issue numbers, semantic fingerprints, versions, paths, source references, and code;
- overlapping entities, malformed Unicode, deep nesting, oversized payloads, binary values, invalid configuration, worker crashes, hangs, and concurrent timeout storms.

No raw provider capture, real personal data, secret, credential, or unsanitized value may be committed.

### Effectiveness measurements

Report by candidate and entity class:

- true positives;
- false positives;
- false negatives;
- precision;
- recall;
- F1;
- recall-weighted F2;
- post-screen escapes;
- raw-value leakage count.

F2 is the primary comparative detection metric because a false negative at the security boundary is more costly than a reviewable additional redaction. F2 does not override the hard gates or information-preservation requirements.

### Information-preservation measurements

Report:

- destructive false positives;
- structural identity mutations;
- schema-validation failures;
- preservation of decision-bearing clauses;
- preservation of provenance and advisory fields;
- percentage of clean samples changed;
- repeated-run output stability.

A detector does not win merely by labeling more spans. It must preserve the meaning needed for downstream evidence, candidate, Recall, and Decision behavior.

### Performance and operational measurements

On a fixed documented environment, report:

- cold-start duration;
- warm p50, p95, and p99 latency;
- throughput;
- peak resident memory;
- worker startup cost;
- package and model size;
- CPU use;
- concurrency behavior;
- timeout recovery;
- orphan-process count;
- offline initialization;
- supported operating systems;
- reproducible installation and pinning;
- dependency, license, and vulnerability posture;
- upgrade and rollback requirements;
- recognizer maintenance burden.

Performance, security, scalability, and availability are co-equal production considerations. Detection quality alone is insufficient.

## Hard gates

A candidate is disqualified when any of the following occurs:

1. A raw sensitive value appears in a receipt, trace, log, error, diagnostic, filename, cursor state, or committed artifact.
2. A known mandatory secret or credential survives sanitization and the postcondition screen.
3. A protected structural identity field changes.
4. Runtime processing makes an undeclared network request.
5. Engine unavailability, invalid configuration, timeout, crash, or unsupported content still emits an envelope or advances a cursor.
6. Identical input, policy, package, model, recognizer, and configuration versions produce nondeterministic sanitized output.
7. Worker cleanup leaves an orphan process.
8. Package, model, recognizer, or configuration provenance cannot be versioned and digest-pinned.
9. License terms are incompatible with Bicameral distribution.
10. The candidate requires an external-ingest receipt-contract change that has not passed the cross-repository protocol process.

No backend failure may silently fall back to a weaker backend.

## Selection rule

The current Bicameral engine remains the alpha selection unless a challenger:

- passes every hard gate;
- materially improves contextual PII coverage;
- preserves or improves mandatory secret and credential protection;
- avoids unacceptable destruction of decision-bearing content;
- remains compatible with the bounded wrapper;
- works fully offline;
- can be packaged and pinned reproducibly;
- provides enough measured benefit to justify dependency, model, memory, startup, and maintenance costs.

The owner decision may:

1. retain the current engine;
2. select an evaluated Presidio configuration;
3. select another evaluated local-first engine;
4. retain the current engine temporarily because no challenger earned replacement;
5. require one bounded follow-up experiment before selection.

## Scoring rubric

Only candidates that pass every hard gate may be comparatively scored.

| Dimension | Weight |
|---|---:|
| Detection recall and F2 | 30 |
| Precision and information preservation | 20 |
| Security and failure behavior | 20 |
| Performance and resource cost | 10 |
| Packaging and operational fitness | 10 |
| Maintainability and replacement seam | 10 |

The score informs the owner decision. It does not mechanically select the winner or override a material safety concern.

## Evaluation implementation

The spike must be stacked from PR #269's exact reviewed head rather than changing the parent branch.

Suggested branch:

```text
spike/redaction-engine-evaluation
```

Suggested draft PR base:

```text
feat/alpha-ingest-real-data-redaction
```

The spike must introduce no production dependency and must not be merged. It exists to produce reproducible decision evidence.

An illustrative backend seam is:

```python
class RedactionBackend(Protocol):
    @property
    def identity(self) -> BackendIdentity:
        ...

    def initialize(self) -> None:
        ...

    def analyze(
        self,
        text: str,
        *,
        field_path: str,
        policy: RedactionPolicy,
    ) -> list[BackendFinding]:
        ...

    def health(self) -> BackendHealth:
        ...
```

Backend-native labels and confidence may appear only in controlled evaluation artifacts. The production receipt remains bounded and value-free.

## Required outputs

The evaluation must produce:

- candidate research and eligibility matrix;
- corpus manifest and digest;
- deterministic evaluation command;
- machine-readable hard-gate results;
- entity-level metric results;
- performance and resource benchmark results;
- dependency, license, and vulnerability inventory;
- representative false-positive and false-negative analysis without exposed sensitive values;
- recommended selection or baseline retention;
- confidence and unresolved uncertainty;
- migration and rollback implications.

Suggested artifact family:

```text
docs/design/redaction-engine-evaluation.md
docs/design/redaction-engine-evaluation-results.md
runtime/redaction_evaluation/
tests/redaction_evaluation/
scripts/evaluate_redaction_backends.py
artifacts/redaction-evaluation/
```

## Consequences

### Positive

- The alpha redaction decision will be supported by Bicameral-shaped evidence rather than framework reputation.
- PR #269's reviewed timeout, isolation, receipt, identity, and failure controls remain useful regardless of the selected detector.
- The repository gains a stable replacement seam for future redaction engines.
- Presidio can earn selection without being presumed correct, while the current engine can remain selected when alternatives do not justify their cost.
- Performance, packaging, vulnerability, and availability tradeoffs become visible before production adoption.

### Negative

- The evaluation introduces short-term spike complexity and candidate-specific development dependencies.
- Large contextual models may require substantial disk, memory, startup, and CI resources.
- Entity-label mapping and deterministic replacement can hide backend differences unless the evaluation artifacts retain enough backend-local evidence.
- The July 29 cut receives less benefit if the evaluation expands into an open-ended framework survey.

### Mitigations

- Time-box candidate discovery through the eligibility screen.
- Require at least three materially different eligible configurations, not every package found on the internet.
- Keep candidate dependencies isolated from production packaging.
- Permit retaining the current engine.
- Defer production migration to a separately governed implementation issue after the owner decision.

## Alternatives considered

### Select Presidio immediately

Rejected. Presidio is a credible candidate, but discussion alone does not establish its effectiveness, information preservation, runtime cost, packaging fit, or operational reliability for Bicameral-shaped data.

### Keep the current engine without evaluation

Rejected as a final decision. The current engine is deterministic and operationally small, but its contextual entity coverage is limited. A bounded comparison is justified before declaring the detector decision closed.

### Replace the entire Bicameral wrapper with a framework-native pipeline

Rejected. The wrapper owns Bicameral-specific identity, timeout, failure, receipt, cursor, and authority contracts. A third-party framework may supply detection but must not become the product boundary.

### Use a hosted PII service

Rejected for the required alpha boundary. It would introduce cost, availability, credential, network, and privacy-boundary dependencies precisely where Bicameral requires local fail-closed processing.

### Run multiple detectors in production and merge their findings

Deferred. Ensemble detection may improve recall but increases nondeterminism, resource use, operational complexity, and conflict resolution. It may be evaluated as a candidate configuration, but it is not the default architecture.

## Governance and release boundaries

This ADR authorizes evaluation only.

It does not:

- select Presidio or any other backend;
- add a production dependency;
- modify PR #262's producer contract;
- change Bot schemas;
- rebind PR #269's information-cycle evidence;
- assign a Release Unit;
- establish merge eligibility;
- create topology, deployment, Product, or human acceptance.

Factory's architecture ledger must remain unchanged until #280 records Kevin's accepted decision. Any selected migration requires a separate implementation issue and governed PR, followed by regenerated tests, receipts, evidence digests, exact-head review, and rollback proof.

## Supporting work

- **#277:** decision parent and acceptance boundary.
- **#278:** candidate matrix, synthetic/sanitized corpus, and metrics contract.
- **#279:** spike-only backend implementations, evaluation, and benchmarks.
- **#280:** owner decision and migration or retention disposition.

## Decision completion

This ADR moves from **Proposed** to **Accepted** only when:

1. the evaluation artifacts are complete and reproducible;
2. all hard-gate results are explicit;
3. Kevin records the selected decision option in #280;
4. the ADR is updated with the exact backend, package/model/configuration pins, rationale, limitations, confidence, and migration disposition;
5. any cross-repository receipt effect is reconciled through the existing protocol process.
