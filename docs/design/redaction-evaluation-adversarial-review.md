# Redaction backend evaluation adversarial review protocol

**Status:** Required review protocol under ADR-0020  
**Owner:** Kevin Knapp  
**Issues:** #277, #280, #285  
**Applies to:** Exact-head output from the comparative spike in #279

## Purpose

This protocol tests whether the redaction-backend comparison is complete, reproducible, candidate-neutral, and safe to place before the owner for a decision.

It does not select a backend. It determines whether the evidence is:

- `not_reviewable`: required evidence is absent, internally inconsistent, biased, or irreproducible;
- `reviewable`: the package can be examined, but unresolved discrepancies prevent an owner decision;
- `owner_decision_ready`: evidence, hard-gate eligibility, metrics, operational costs, and uncertainty are sufficiently complete for Kevin to decide under #280.

A high comparative score cannot override a failed hard gate.

## Required review bindings

The review result must bind to:

- repository and pull-request number;
- exact 40-character spike head SHA;
- exact base ref and parent PR #269 head;
- corpus manifest SHA-256;
- corpus aggregate SHA-256;
- candidate matrix SHA-256;
- candidate configuration digests;
- hard-gate artifact SHA-256;
- metrics artifact SHA-256;
- benchmark artifact SHA-256;
- dependency, license, and vulnerability artifact digests;
- recommendation artifact SHA-256;
- review-result SHA-256.

A changed input invalidates the review. Do not carry a verdict forward to a different exact head.

## Preconditions

Before review begins, confirm:

- [ ] ADR-0020 is the governing decision record.
- [ ] The spike targets the governed parent branch rather than `main`.
- [ ] The spike is unmerged.
- [ ] The corpus and expected annotations pass the repository contract validator.
- [ ] All result artifacts are regenerated from one documented command.
- [ ] Candidate package, model, recognizer, mapping, and configuration versions are pinned.
- [ ] Required repository checks have completed.
- [ ] No raw provider capture, real personal information, credential, or secret is present.

Failure of a precondition produces `not_reviewable`.

## Review area A: candidate discovery and selection bias

- [ ] Candidate research uses primary sources.
- [ ] The current Bicameral engine is evaluated as the baseline.
- [ ] Presidio is not treated as the presumed winner.
- [ ] At least three materially different eligible configurations are executed.
- [ ] A credible lightweight local-first alternative was investigated.
- [ ] Candidates rejected before implementation have explicit evidence and a valid disqualifier.
- [ ] Hosted services are comparison references only and are not presented as alpha-eligible.
- [ ] Candidate discovery was time-bounded without excluding a materially stronger obvious option.
- [ ] Candidate-specific dependencies remain evaluation-only.

Record any candidate omitted for convenience rather than evidence as a blocker.

## Review area B: corpus and annotation neutrality

- [ ] Manifest and expected records validate against the accepted closed schemas.
- [ ] All manifest digests match exact file bytes.
- [ ] Record IDs, paths, entity IDs, and assertion IDs are unique.
- [ ] Manifest ordering is deterministic.
- [ ] No unlisted corpus or expected JSON file exists.
- [ ] Positive cases cover required sensitive-data classes.
- [ ] Negative controls include Bicameral identifiers that resemble PII.
- [ ] Decision-preservation cases contain meaningful requirements, proposals, constraints, or Decisions.
- [ ] GitHub, Linear, local-directory, bounded-document, Observation, AdapterEmission, and ExternalIngestEnvelope shapes are represented.
- [ ] Failure fixtures cover unavailable, invalid, crash, timeout, malformed finding, and concurrency paths.
- [ ] Annotations were not changed after candidate results were observed without a separately reviewed corpus revision.
- [ ] Corpus classes do not disproportionately favor one detector architecture.
- [ ] Span offsets, matching rules, and category mappings are candidate-neutral.

A post-result annotation change without independent review produces `not_reviewable`.

## Review area C: hard-gate integrity

Independently verify every candidate result for:

- [ ] no raw leakage;
- [ ] mandatory secret and credential protection;
- [ ] protected identity preservation;
- [ ] no undeclared runtime network request;
- [ ] fail-closed unavailable behavior;
- [ ] fail-closed invalid-configuration behavior;
- [ ] fail-closed crash behavior;
- [ ] fail-closed timeout behavior;
- [ ] no envelope emission on failure;
- [ ] no cursor advancement on failure;
- [ ] deterministic output and normalized findings;
- [ ] bounded worker cleanup with no orphan process;
- [ ] package, model, recognizer, mapping, and configuration pinning;
- [ ] compatible license posture;
- [ ] production receipt compatibility.

The review must confirm that failed candidates remain visible but are marked ineligible. Aggregate metrics must not conceal a mandatory failure.

## Review area D: metric reproducibility

- [ ] TP, FP, and FN counts can be regenerated from record-level output.
- [ ] Matching is deterministic maximum-overlap matching.
- [ ] One candidate detection maps to at most one expected entity.
- [ ] One expected entity maps to at most one candidate detection.
- [ ] Exact-span accuracy is reported separately.
- [ ] Precision, recall, F1, and F2 use the accepted formulas.
- [ ] Zero denominators produce `null` plus a typed explanation.
- [ ] Metrics are broken down by category, subtype, source shape, and corpus class.
- [ ] Destructive false positives and clean-record modifications are reported.
- [ ] Decision-preservation failures are visible at record level.
- [ ] Protected-field mutations and schema failures are visible at record level.
- [ ] Weighted scores are recomputable from eligible candidates only.
- [ ] Scoring does not mechanically select a winner.

Any unreproducible aggregate produces `not_reviewable`.

## Review area E: performance and non-functional requirements

- [ ] The benchmark host and operating environment are exact and complete.
- [ ] Cold initialization is separated from warm request latency.
- [ ] p50, p95, and p99 are computed from disclosed sample counts.
- [ ] Small, medium, large, and maximum-admitted payload classes are separate.
- [ ] Throughput, CPU, peak resident memory, worker startup, and timeout recovery are reported.
- [ ] Package and model artifact sizes are measured rather than estimated.
- [ ] Concurrency behavior and orphan-process counts are tested.
- [ ] Offline execution denies or intercepts outbound access after provisioning.
- [ ] Attempted network calls are reported, not discarded.
- [ ] Supported operating systems and Python versions are explicit.
- [ ] Upgrade, rollback, model acquisition, and cache behavior are documented.
- [ ] Availability and initialization failure modes are included.

Missing material operational costs prevent `owner_decision_ready`.

## Review area F: dependency, license, and security posture

- [ ] Direct and transitive dependencies are listed.
- [ ] Package and model hashes are present.
- [ ] Licenses and redistribution obligations are stated.
- [ ] Known vulnerabilities are evaluated at exact versions.
- [ ] Unsupported or abandoned dependencies are identified.
- [ ] Model training-data and evaluation limitations are disclosed when available.
- [ ] No package or model downloads occur silently at runtime.
- [ ] Candidate configuration can be reproduced without mutable latest-version references.

A materially incompatible license or unpinnable artifact is a hard-gate failure.

## Review area G: recommendation honesty

- [ ] The recommendation distinguishes measurements from inference.
- [ ] The recommendation distinguishes inference from owner judgment.
- [ ] Failed hard gates are named before comparative scores.
- [ ] Retaining the current engine remains a valid result.
- [ ] The measured improvement is compared against memory, startup, package, model, maintenance, and vulnerability costs.
- [ ] Known uncertainty is explicit.
- [ ] Migration and rollback implications are explicit.
- [ ] No evaluation evidence is described as production, deployment, topology, Product, or human acceptance.
- [ ] The recommendation does not update Factory architecture or PR #269 by implication.

Promotional language unsupported by measurements prevents `owner_decision_ready`.

## Verdict rules

### `not_reviewable`

Use when any of the following is true:

- a precondition fails;
- corpus or annotation integrity is invalid;
- required artifacts are absent;
- aggregate metrics cannot be reproduced;
- exact candidate or model identity is unknown;
- review inputs are not bound to an exact head;
- raw sensitive material appears in review artifacts;
- candidate eligibility is inconsistent with hard-gate results.

### `reviewable`

Use when the package is internally valid and reproducible, but a bounded discrepancy or missing comparison prevents the owner decision.

Every discrepancy must name:

- severity;
- exact evidence path;
- affected candidate or record IDs;
- whether new implementation is required;
- whether owner judgment is required.

### `owner_decision_ready`

Use only when:

- all required evidence exists;
- all aggregates reproduce;
- candidate eligibility matches hard-gate results;
- operational and security costs are complete;
- unresolved uncertainty is explicit;
- no blocker remains;
- the owner decision packet can bind to the exact reviewed artifacts.

## Review-result template

Create `artifacts/redaction-evaluation/adversarial-review.json` conforming to:

`tests/redaction_evaluation/schema/adversarial-review.schema.json`

The result must contain no raw sensitive value. Evidence references must be repository-relative artifact references or immutable GitHub references.

## Authority boundary

This review can declare evidence `owner_decision_ready`. It cannot:

- select a backend;
- accept a migration;
- modify PR #269 or PR #262;
- update Factory architecture;
- assign a Release Unit;
- establish merge eligibility;
- create topology, deployment, Product, or human acceptance.
