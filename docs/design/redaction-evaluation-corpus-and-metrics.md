# Redaction evaluation corpus and metrics contract

**Status:** Proposed implementation contract for ADR-0020
**Owner:** Kevin Knapp
**Parent issue:** #277
**Research/corpus issue:** #278
**Comparative spike issue:** #279
**Decision issue:** #280

## Purpose

Define one candidate-neutral corpus, annotation model, metric calculation, and hard-gate result format for comparing local-first redaction engines behind the Bicameral-owned boundary.

This contract is deliberately independent of Presidio, GLiNER, the current Bicameral engine, or any other candidate. A candidate must adapt to the contract. The contract must not be rewritten to flatter a candidate.

## Evaluation boundary

Every candidate is invoked through the same logical path:

```text
test record
  -> Bicameral admitted-field and identity policy
  -> candidate detector backend
  -> Bicameral deterministic replacement policy
  -> existing hard-screen postcondition
  -> candidate-neutral result
```

Candidate-specific entity names, confidence scores, and model metadata may be preserved in diagnostic evaluation output. They do not alter expected labels or the production receipt contract.

## Corpus manifest

The corpus root must contain a machine-readable manifest with this minimum shape:

```json
{
  "schema_version": 1,
  "corpus_id": "bicameral-redaction-evaluation-v1",
  "description": "Synthetic and irreversibly sanitized evaluation records",
  "records": [
    {
      "record_id": "decision-with-person-email-001",
      "source_shape": "observation",
      "input_path": "records/decision-with-person-email-001.json",
      "expected_path": "expected/decision-with-person-email-001.json",
      "classes": ["pii", "decision_preservation"],
      "input_sha256": "...",
      "expected_sha256": "..."
    }
  ]
}
```

All paths are repository-relative. Every input and expected file must be digest-pinned. Manifest ordering must be deterministic.

## Record classes

The corpus must cover at least these classes:

### Positive detection

- person names;
- email addresses;
- telephone numbers in multiple valid forms;
- physical and postal addresses;
- birth dates;
- government identifiers;
- financial identifiers;
- credentials, tokens, and secrets;
- health-related identifiers;
- account identifiers;
- IP addresses;
- mixed and overlapping entities;
- nested metadata values.

### Bicameral source and wire shapes

- GitHub webhook issue and comment records;
- GitHub polling records;
- Linear webhook records;
- Linear GraphQL records;
- local-directory imports;
- bounded document-fetch records;
- provider-neutral `Observation`;
- `AdapterEmission`;
- `ExternalIngestEnvelope`.

### Decision-preservation

Records must contain a meaningful requirement, proposal, constraint, or Decision adjacent to sensitive material. Expected output must preserve the decision-bearing clause while replacing only the sensitive spans.

### Negative controls

Records must include clean values that resemble sensitive data but must remain unchanged:

- Git SHAs;
- UUIDs;
- RFC3339 timestamps;
- issue and PR references;
- semantic fingerprints;
- contract and receipt IDs;
- versions;
- URLs;
- repository and file paths;
- code snippets;
- harmless numeric identifiers;
- provider resource identifiers.

### Failure and resilience

- unsupported binary values;
- oversized payloads;
- malformed Unicode;
- deeply nested metadata;
- sensitive metadata keys;
- invalid candidate configuration;
- unavailable package or model;
- candidate initialization failure;
- processing exception;
- processing timeout;
- worker crash;
- concurrent timeout storm;
- overlapping or malformed candidate spans;
- nondeterministic candidate output.

## Expected annotation format

Each expected record must contain:

```json
{
  "schema_version": 1,
  "record_id": "decision-with-person-email-001",
  "expected_entities": [
    {
      "entity_id": "entity-001",
      "category": "pii",
      "subtype": "person",
      "field_path": "title",
      "start": 0,
      "end": 11,
      "replacement": "[redacted:person]",
      "mandatory": false
    }
  ],
  "protected_fields": [
    {
      "field_path": "provider_event_id",
      "expected_value_sha256": "..."
    }
  ],
  "preservation_assertions": [
    {
      "assertion_id": "decision-clause-001",
      "field_path": "excerpt",
      "required_substring": "approved keeping the event store local"
    }
  ],
  "expected_outcome": "sanitized",
  "expected_failure_reason": null
}
```

Raw sensitive values must never be copied into aggregate result artifacts. Span offsets and expected values may exist only inside the synthetic or irreversibly sanitized corpus records.

## Category normalization

Backend-native labels map into these candidate-neutral categories:

- `secret`;
- `credential`;
- `pii`;
- `phi`;
- `prohibited_content`.

The expected annotation may retain a non-authoritative subtype such as `person`, `email`, `phone`, `address`, `government_id`, or `financial_id` for evaluation detail.

Mapping rules must be explicit, versioned, and included in the candidate configuration digest.

## Matching rules

A detection is a true positive when:

1. candidate and expected field paths match;
2. normalized categories match;
3. the detected span overlaps the expected span using the configured overlap rule;
4. one candidate detection is matched to at most one expected entity;
5. one expected entity is matched to at most one candidate detection.

Use deterministic maximum-overlap matching. Exact span match must be reported separately from category-level match.

Mandatory secrets and credentials are evaluated independently from general PII. A mandatory secret or credential that survives the Bicameral postcondition is a hard-gate failure regardless of aggregate score.

## Metrics

For each candidate, entity category, subtype, source shape, and corpus class, calculate:

- true positives;
- false positives;
- false negatives;
- precision;
- recall;
- F1;
- F2;
- exact-span accuracy;
- destructive false-positive count;
- clean records modified;
- decision-preservation failures;
- protected-field mutations;
- schema-validation failures;
- post-screen escapes;
- raw-value leakage findings;
- repeated-output mismatches.

Use the conventional definitions:

```text
precision = TP / (TP + FP)
recall = TP / (TP + FN)
F1 = 2 * precision * recall / (precision + recall)
F2 = 5 * precision * recall / (4 * precision + recall)
```

When a denominator is zero, emit `null` plus a typed explanation. Do not silently emit zero or one.

## Decision-preservation metric

A record passes decision preservation only when:

- every required preservation assertion remains present after sanitization;
- the output remains schema valid;
- no protected identity field changes;
- sanitization does not remove the complete sentence or field containing the decision unless the field is required to fail closed.

Report the number and percentage of decision-preservation records passed.

## Determinism

For each candidate and record:

- initialize from the same pinned configuration;
- run at least five repeated warm executions;
- compare canonical sanitized output;
- compare normalized findings;
- compare receipt-domain fields excluding explicitly variable timing fields.

Any unexplained mismatch is a hard-gate failure.

## Performance contract

Measure on one documented host environment:

- cold initialization duration;
- warm p50, p95, and p99 latency;
- throughput;
- peak resident memory;
- worker startup cost;
- installed package size;
- model artifact size;
- timeout recovery duration;
- orphan-process count.

Report results separately for small, medium, large, and maximum-admitted payloads. Do not combine cold initialization with warm request latency.

## Offline execution proof

After all packages and models are provisioned, run the evaluation with outbound network access denied or intercepted. Record every attempted connection. An undeclared runtime network attempt is a hard-gate failure.

## Hard-gate result format

Each candidate must emit:

```json
{
  "candidate_id": "presidio-spacy-v1",
  "passed": false,
  "gates": [
    {
      "gate_id": "no-runtime-network",
      "status": "passed",
      "evidence": ["artifact:offline-network-trace"]
    },
    {
      "gate_id": "identity-preservation",
      "status": "failed",
      "affected_record_ids": ["record-123"],
      "raw_values_included": false
    }
  ]
}
```

Required hard gates:

- no raw leakage;
- mandatory secret and credential protection;
- identity preservation;
- no undeclared runtime network;
- fail-closed unavailable/crash/timeout behavior;
- no cursor advancement or envelope emission on failure;
- deterministic output;
- bounded cleanup with no orphan process;
- package/model/configuration pinning;
- compatible licensing;
- production receipt compatibility.

A candidate failing any hard gate remains visible in comparison output but is ineligible for selection.

## Candidate summary format

The machine-readable summary must include:

- candidate identity and backend family;
- exact package versions;
- exact model and recognizer versions;
- configuration digest;
- corpus digest;
- hard-gate result;
- quality metrics;
- preservation metrics;
- performance metrics;
- dependency and license posture;
- known limitations;
- selection eligibility.

## Scoring

Only candidates passing every hard gate receive a weighted comparative score:

- detection recall and F2: 30%;
- precision and information preservation: 20%;
- security and failure behavior: 20%;
- performance and resource cost: 10%;
- packaging and operational fitness: 10%;
- maintainability and replacement seam: 10%.

The weighted score is advisory. The final decision must explain why the measured benefit does or does not justify migration.

## Reproducibility

One top-level command must regenerate:

- corpus validation;
- candidate matrix;
- hard-gate results;
- quality metrics;
- determinism results;
- benchmark results;
- dependency/license inventory;
- recommendation draft.

The command must fail non-zero when:

- corpus or expected digests drift;
- an annotation is malformed;
- required candidate output is missing;
- a hard-gate artifact is absent;
- aggregate metrics cannot be reproduced.

## Governance boundary

This contract creates evaluation evidence only. It does not select a backend, add a production dependency, modify the production receipt, rebind PR #269 evidence, alter PR #262, update Factory architecture, or grant release, topology, deployment, Product, or human acceptance authority.
