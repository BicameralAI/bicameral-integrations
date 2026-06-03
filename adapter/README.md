# Universal Adapter

The universal adapter is Bicameral-facing. It converts connector observations
into neutral `AdapterEmission` objects with preserved source evidence.

Provider-specific behavior belongs in `connectors/`. The adapter owns the
normalization contract, validation rules, shared filters, fixture helpers, and
pipeline shape.

