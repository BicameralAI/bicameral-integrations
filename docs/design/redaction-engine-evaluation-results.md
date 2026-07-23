# Redaction engine evaluation results

**Status:** Evaluation evidence for ADR-0020 (issues #278, #279)
**Owner:** Kevin Knapp
**Evaluation date:** 2026-07-23
**Corpus:** `bicameral-redaction-evaluation-v1`, 101 records, digest `sha256:121b8cf9c1b641cd9d26870e93012b92075cb4f2c63bb8097f3cc81ed309b47c`
**Baseline branch point:** PR #269 exact head `fd69ff2742363b5d619bc073b8e8490c0f50733d`
**Machine-readable artifacts:** `artifacts/redaction-evaluation/`
**Regeneration:** `python scripts/evaluate_redaction_backends.py all` (fails non-zero on digest drift, malformed annotations, missing outputs, or unreproducible aggregates)

Every candidate ran behind the same Bicameral-owned evaluation harness that
mirrors the production wrapper in `adapter/core/redaction_receipt.py`: the
wrapper keeps admitted-field policy, identity preservation, deterministic
replacement, the hard-screen postcondition, typed fail-closed reasons, and
no-envelope/no-cursor failure semantics. Candidates supplied detection only.

## Implemented configurations

| Candidate | Detector | Model weight |
|---|---|---|
| `bicameral-stdlib-v1` | Production catalog + email/phone regexes (stdlib only) | none |
| `presidio-spacy-lg-v1` | presidio-analyzer 2.2.364, spaCy `en_core_web_lg` 3.8.0, explicit recognizer registry, Bicameral secret/PHI recognizers, no URL recognizer | 382 MB |
| `presidio-gliner-pii-v1` | presidio-analyzer 2.2.364 GLiNERRecognizer, `urchade/gliner_multi_pii-v1` at revision `1fcf13e8`, 12 pinned labels, threshold 0.45, plus Bicameral secret/PHI and email/credit-card recognizers | 1.16 GB |
| `datafog-regex-v1` | datafog 4.8.0 regex engine, standalone | none |

Full pinned configurations, label maps, and configuration digests are recorded
per candidate in `artifacts/redaction-evaluation/candidate-results/`.

## Hard gates

All four candidates passed every computable hard gate in the corpus run:

- no raw sensitive value in any result artifact (verified by scanning every
  serialized result document against the raw expected span values);
- no mandatory secret or credential surviving into emitted sanitized output
  (the wrapper's hard screen rejected every record whose secrets a weak
  detector missed, so weak detection loses records rather than leaking them);
- byte-stable protected identity fields, zero mutations;
- fail-closed behavior for unavailable engine, invalid configuration, crash,
  hang, worker death, malformed spans, oversized payload, binary content,
  malformed Unicode, and sensitive metadata keys, each with the typed reason
  the corpus expected (15/15 failure fixtures agree for every candidate);
- no envelope emission and no cursor advance on any failure;
- deterministic output across 5 repeated warm executions per record, zero
  mismatches for all candidates (and the nondeterminism probe was correctly
  rejected);
- bounded cleanup: the 8-way concurrent timeout storm terminated every hung
  worker inside the budget plus tolerance, zero orphan processes, and a
  healthy call succeeded immediately afterwards;
- offline execution with socket-level network denial: see the offline section;
- provenance pinned (packages, models, recognizers, label maps, and policy all
  participate in each candidate's configuration digest);
- production receipt shape reproducible and value-free for every candidate.

`artifacts/redaction-evaluation/hard-gates.json` holds the per-gate,
per-candidate evidence.

## Detection quality (corpus totals)

F2 is the primary comparative metric per ADR-0020; it never overrides hard
gates or preservation.

| Candidate | TP | FP | FN | Precision | Recall | F1 | F2 | Exact span |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `bicameral-stdlib-v1` | 56 | 0 | 53 | 1.000 | 0.514 | 0.679 | 0.569 | 55/56 |
| `presidio-spacy-lg-v1` | 99 | 16 | 10 | 0.861 | 0.908 | 0.884 | 0.898 | 89/99 |
| `presidio-gliner-pii-v1` | 101 | 12 | 8 | 0.894 | 0.927 | 0.910 | 0.920 | 99/101 |
| `datafog-regex-v1` | 42 | 6 | 67 | 0.875 | 0.385 | 0.535 | 0.434 | 42/42 |

Per-category, per-subtype, per-source-shape, and per-class breakdowns are in
`artifacts/redaction-evaluation/metrics.json` and `entity-results.csv`.

### Where the differences come from (no values exposed)

- The baseline's 53 false negatives are entirely contextual classes it has no
  detector for: person names (30), addresses (7), bare IP addresses (7),
  account identifiers (4), prose dates of birth (2), unlabeled government
  identifiers (2), IBAN (1). Its precision is perfect: zero false positives
  across all negative controls.
- `presidio-spacy-lg-v1` recovers persons (27/30), all addresses, all IPs,
  and all phones/emails, while the Bicameral catalog recognizers keep every
  secret detection. Its 16 false positives are concentrated in LOCATION
  over-tagging (9) and person over-tagging (7); none were destructive (no
  overlap with decision-bearing clauses, no negative-control record
  modified). Residual misses: account identifiers (4), prose DOB (2), three
  person names, one unlabeled government id.
- `presidio-gliner-pii-v1` has the best recall and F2: all persons, all
  addresses, all phones. Its notable weakness is bare IP addresses (1/7
  detected): the pinned zero-shot "ip address" label under-fires at the 0.45
  threshold. 12 false positives (7 person, 2 address, 2 account, 1 phone), of
  which 2 were destructive (they overlapped required decision substrings),
  and one decision-preservation record failed as a result.
- `datafog-regex-v1` detects structured classes only (emails, phones, IPs,
  Luhn cards, one labeled SSN form) and none of the 19 mandatory catalog
  secrets in the corpus. Every secret-bearing record therefore failed closed
  at the wrapper's hard screen: nothing leaked, but the records were lost,
  which is exactly the availability cost of a weak detector behind a
  fail-closed boundary. It also flagged 5 date-like spans as DOB, modifying
  2 clean negative-control records.

### Mandatory secret and credential protection

Zero post-screen escapes for every candidate. For the two Presidio
configurations this is achieved by detection (the Bicameral catalog
recognizers run inside the candidate); for datafog it is achieved by
rejection (the wrapper refused 19 mandatory entities' records). The
protection property held universally; the difference is whether the record
survives sanitization.

## Information preservation

| Candidate | Decision preservation | Destructive FP | Clean records modified | Protected-field mutations | Schema failures | Repeat mismatches |
|---|---|---:|---:|---:|---:|---:|
| `bicameral-stdlib-v1` | 8/8 | 0 | 0 | 0 | 0 | 0 |
| `presidio-spacy-lg-v1` | 8/8 | 0 | 0 | 0 | 0 | 0 |
| `presidio-gliner-pii-v1` | 7/8 | 2 | 0 | 0 | 0 | 0 |
| `datafog-regex-v1` | 6/8 | 2 | 2 | 0 | 0 | 0 |

## Performance and operational benchmarks

Benchmark environment, cold/warm separation, payload classes, memory, CPU,
concurrency, timeout recovery, and package/model sizes are recorded in
`artifacts/redaction-evaluation/benchmark-results.json` and
`environment.json`. See the summary table in
`artifacts/redaction-evaluation/recommendation.md`.

## Offline execution proof

Each candidate was initialized and exercised in a fresh process with
socket-level network denial (connect, connect_ex, create_connection,
getaddrinfo all patched to record and refuse). Results in
`artifacts/redaction-evaluation/offline-proof.json`.

## Dependency, license, and vulnerability posture

Machine-readable inventories: `dependency-report.json`, `license-report.json`,
`vulnerability-report.json`. Notable grounded findings:

- torch CVE-2025-32434 (`torch.load` RCE, fixed in 2.6.0) is the controlling
  advisory for the GLiNER lane because the pinned model ships only a
  `pytorch_model.bin`; the evaluation environment runs torch 2.13.0 (safe),
  and any production adoption must keep the >=2.6 floor plus the commit
  pin.
- transformers 5.6.2 is past the CVE-2025-6921 fix line.
- Presidio packages and base spaCy have zero OSV advisories.
- The GLiNER model's backbone tokenizer (`microsoft/mdeberta-v3-base`) is
  loaded by gliner transitively and its revision is not pinnable through the
  gliner API; the cached snapshot is deterministic offline, but this is a
  provenance gap to close in any production adoption.
- The license report flags MPL-2.0 (`certifi`) in the Presidio closures as
  `review_required` under the never-guess rule; MPL-2.0 file-level copyleft
  is conventionally compatible with distribution, but the call is recorded
  for review rather than silently passed.

## Limits of this evaluation

- The corpus is synthetic. Absolute recall/precision numbers will differ on
  real provider traffic; the comparative ordering is the evidence product.
- All measurements are from one pinned Windows host environment; determinism
  across platforms is explicitly not claimed for the model-based lanes.
- The GLiNER lane was measured at one threshold (0.45) with one pinned label
  set; threshold sweeps were out of scope.
- In-process latency for real candidates is advisory; hard timeout
  enforcement was proven separately through the worker-process harness.
