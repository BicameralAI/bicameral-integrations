# Universal Adapter

The universal adapter is Bicameral-facing. It converts connector observations
into neutral `AdapterEmission` objects with preserved source evidence.

Provider-specific behavior belongs in `connectors/`. The adapter owns the
normalization contract, validation rules, shared filters, fixture helpers, and
pipeline shape.

## Sensitive-data handling

- `core/sensitive.py` — the FX-SEC-001 catalog (`detect_sensitive`): secret / PHI / PAN
  detection. `pipeline._screen_sensitive` HARD-rejects any emission that trips it
  (fail-closed backstop, never bypassed).
- `core/redaction.py` — `redact(text)`: the **redact-and-pass** primitive. Scrubs the catalog
  classes (value-consuming `redact_catalog`) plus email/phone to placeholders so PII-dense
  free-text can be emitted as evidence; invariant `detect_sensitive(redact(x)) == []`. Composes
  with — never replaces — the screen. See [`docs/DATA_CLASSIFICATION_AND_REDACTION.md`](../docs/DATA_CLASSIFICATION_AND_REDACTION.md).

