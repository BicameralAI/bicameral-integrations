# Redaction evaluation corpus

Candidate-neutral evaluation corpus for comparing local-first redaction
engines behind the Bicameral-owned boundary (ADR-0020 corpus/metrics
contract). The corpus is independent of any specific detector backend: a
candidate must adapt to this contract, never the reverse.

- Corpus id: `bicameral-redaction-evaluation-v1`
- 101 records, digest-pinned by `corpus-manifest.json`
  (validates against `schema/corpus-manifest.schema.json`)
- Expected annotations in `expected/` (each validates against
  `schema/expected-record.schema.json`)
- Inputs in `corpus/`, one JSON record per file, named `<record_id>.json`

## Regeneration

```
python tests/redaction_evaluation/generate_corpus.py
```

The generator is fully deterministic (no timestamps, no randomness); running
it twice produces byte-identical output. It ends by re-validating everything
it wrote: digest pinning, span resolution, loader round-trip, optional
jsonschema validation, and a committed-byte scan with the repository
sensitive-data catalog (`adapter/core/sensitive.py`).

`test_evaluation_contract.py` enforces the same contract in CI, with a
dependency-free structural fallback when `jsonschema` is not installed.

## Synthetic-data guarantee

Every value in this corpus is fabricated. No real person, account,
credential, address, or clinical identifier appears anywhere:

- names are invented ("Avery Winslow", "Rowan Ellery", ...);
- email addresses use `example.com` / `example.org`;
- phone numbers use the NANP 555-01xx fiction range plus fabricated
  international forms;
- postal addresses are fictional;
- IP addresses come from documentation ranges (192.0.2.0/24, 2001:db8::/32);
- payment cards are the industry-standard Luhn-valid test numbers only;
- the IBAN is the standard GB82 WEST test value;
- secret-shaped tokens match the shapes in the repository catalog but are
  built from obviously synthetic bodies (repeated "Example"/zero filler);
- clinical identifiers are invented digit runs attached to synthetic labels.

## Record classes

Class membership is recorded per record in the manifest (a record may carry
several classes). Current distribution:

| Class | Records | Meaning |
| --- | --- | --- |
| `positive_detection` | 72 | at least one expected entity span |
| `structural_identity` | 21 | provider identity fields pinned via `protected_fields` |
| `nested_metadata` | 22 | entities (or the fixture point) live inside nested metadata |
| `negative_control` | 14 | sensitive-looking but clean; expected outcome `unchanged` |
| `decision_preservation` | 8 | a decision/requirement/constraint/proposal clause must survive sanitization |
| `mixed_entities` | 3 | several entity categories in one record |
| `overlapping_entities` | 2 | adjacent/nested entity shapes with disjoint gold spans |
| failure/resilience classes | 16 | `malformed_input`, `oversized_payload`, `unsupported_binary`, `sensitive_metadata_key`, `backend_*`, `concurrency_timeout_storm`, `malformed_backend_findings`, `nondeterminism_probe` |

Source shapes cover plain text, provider-neutral observations, GitHub
webhook/poll payloads, Linear webhook/GraphQL payloads, local-directory
imports, bounded document fetches, adapter emissions, external ingest
envelopes, and failure fixtures. Provider-shaped documents sit inside
`observation.metadata` under realistic keys (for example
`metadata.webhook.issue.body`) so nested sanitization is exercised.

## Input record format

```json
{
  "record_id": "...",
  "source_shape": "...",
  "observation": {
    "source_ref": {"source_id": "...", "ref": "...", "url": "...", "kind": "..."},
    "excerpt": "...", "title": "...", "author": "...", "mode": "active",
    "timestamp": "...", "provider_event_id": "...",
    "provider_resource_id": "...", "evidence_id": "...",
    "evidence_metadata": {}, "metadata": {}
  },
  "eval_directives": {}
}
```

`eval_directives` is present only on failure fixtures:

- `{"fault": "..."}` instructs the harness to inject the named backend fault
  (invalid configuration, missing model, init failure, exception, hang,
  worker crash, timeout storm, malformed spans, nondeterminism);
- `{"binary_field": {"path": ..., "base64": ...}}` instructs the harness to
  convert the referenced value to raw bytes before sanitization;
- `{"obfuscated_object": {"path": ..., "b64rev": ...}}` carries a whole
  object in obfuscated form (see below); the loader decodes and installs it.

## field_path convention

Paths are dot-joined from the observation root: `excerpt`, `title`,
`author`, `source_ref.source_id`, `metadata.webhook.issue.body`,
`evidence_metadata.note`; list items use bracket indexes, for example
`metadata.comments[0].body`. Entity `start`/`end` are character offsets into
the de-obfuscated string value at that path. `corpus_loader.resolve_field_path`
implements the resolution rule.

## Obfuscation scheme

No secret-shaped raw token may exist in committed repository bytes (the
repository secret scan and the catalog scan in the contract test both
enforce this). Any string field whose plain text would trip the sensitive
catalog (secret tokens, Luhn-valid card numbers, labeled clinical values) is
committed as:

```json
{"__b64rev__": "<base64 of the UTF-8 encoding of the reversed string>"}
```

`corpus_loader.deobfuscate` restores the original text (base64-decode, then
reverse). Expected span offsets always index the decoded text. Ordinary PII
text (names, emails, phones, addresses) stays plain for reviewability.

For the two fixtures where a metadata *key* is itself sensitive, the whole
containing object is committed as the base64 of the reversed canonical JSON
of that object inside an `obfuscated_object` directive, and the committed
`observation.metadata` placeholder stays empty. `corpus_loader.load_input_record`
decodes the directive and installs the object at the directive path.

## Annotation model

- `category`: `secret`, `credential`, `pii`, `phi` (`prohibited_content`
  reserved). Secrets and the card-number credential class are
  `mandatory: true`; labeled clinical values are `mandatory: true`; general
  PII is `mandatory: false`.
- `replacement` is always `[redacted:<subtype>]`.
- `protected_fields` pin provider identity values (source ref, provider
  event/resource ids, evidence id, timestamp) by SHA-256 of their UTF-8
  bytes; these values must survive sanitization byte-for-byte.
- `preservation_assertions` name decision-bearing substrings that must
  remain after sanitization; gold substrings never overlap entity spans.
- Author fields carry display names annotated as person PII where present;
  pseudonymous provider logins are deliberately left unannotated.

## Loading

```python
from tests.redaction_evaluation.corpus_loader import (
    iter_manifest, load_input_record, resolve_field_path,
)
```

The loader is stdlib-only and shared by the contract tests and the runtime
evaluation harness.
