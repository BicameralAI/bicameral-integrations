# Provider Acquisition — Golden Fixtures

Provisional alpha golden fixtures for the `ProviderResourceDescriptor` and
`ProviderItemEnvelope` types defined in
[BicameralAI/bicameral-bot#462](https://github.com/BicameralAI/bicameral-bot/issues/462).

## Authority boundary

These fixtures are **provider facts**, not Bicameral evidence or governance
objects. They do not carry:

- `SourceBinding` approval or `Source` materialization
- `SourceSnapshot` or `SourceEvidence` state
- `DecisionCandidate`, `Decision`, review commands, or signoff
- Local actor/session authority (`AuthorityContext`)
- Event-store write intent or bot lifecycle authority

Provider acquisition objects enter governance only after explicit promotion
through the existing `SourceBinding` path.

## Structure

```text
protocol/provider_acquisition/
├── schemas/                          # Reference copies of bot v2 schemas
│   ├── provider-resource-descriptor.schema.json
│   └── provider-item-envelope.schema.json
├── fixtures/
│   ├── descriptors/                  # Golden ProviderResourceDescriptor examples
│   │   ├── linear-*.json
│   │   ├── google-drive-*.json
│   │   └── github-*.json
│   └── items/                        # Golden ProviderItemEnvelope examples
│       ├── linear-*.json
│       └── github-*.json
├── tests/
│   ├── test_fixture_schema_conformance.py
│   └── test_fixture_secret_guard.py
└── README.md
```

## Validation

```bash
pytest -q protocol/provider_acquisition/tests/
```

## Schema provenance

Schemas copied from `BicameralAI/bicameral-bot` `protocol/schemas/v2/` at the
commit that merged PR #467 (bot#462 implementation). These are reference copies
for offline fixture validation; the bot repo remains the schema source of truth.
