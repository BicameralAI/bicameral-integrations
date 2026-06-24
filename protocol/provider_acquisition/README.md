# Provider Acquisition — Discovery Surface

Provisional alpha golden fixtures + discovery connectors for the
`ProviderResourceDescriptor` and `ProviderItemEnvelope` types defined in
[BicameralAI/bicameral-bot#462](https://github.com/BicameralAI/bicameral-bot/issues/462).

Connectors:

- `stub.py` — `FixtureDiscoveryStub`: fixture-backed emitter for contract-shape /
  downstream integration testing (#178).
- `github/` — `GitHubDiscoveryConnector`: GitHub App **installation-only** discovery
  over an injected transport + token provider (#180). Mocked/recorded slice — the
  live `urllib` transport + App-key handling are hosted-side (cloud#7) and out of
  scope; recorded GitHub REST responses live under `fixtures/recorded/github/` (so
  the secret-guard's `rglob` covers them). See ADR-0017 Addendum 2026-06-23.
- `google_drive/` — `GoogleDriveDiscoveryConnector`: shared-drive + `.bicameral`
  project-folder discovery and document-leaf fetch (#179). Mocked/recorded slice —
  the live `urllib` transport + OAuth refresh are operator-side
  (`runtime.google_oauth.RefreshTokenSecretResolver`) and out of scope (factory#93).
  Reuses the runtime `SecretResolver` as the token provider (no new type) and
  `screening.py`; recorded Drive REST responses live under
  `fixtures/recorded/google_drive/`. Local transport mirror of `github/` (unification
  deferred). See ADR-0017 Addendum 2026-06-23 (#179).
- `linear/` — `LinearDiscoveryConnector`: workspace → team → project → issue
  discovery + issue/comment item fetch over Linear's **GraphQL** API (ADR-0017 alpha
  3/3). Mocked/recorded — the live GraphQL POST is operator-side and deferred. Reuses
  the runtime `SecretResolver` as the API-key provider (**raw `Authorization`, no
  Bearer**) and `screening.py`; reuses `connectors.linear.connector.parse_issue_node`
  for issue content. GraphQL fail-closed (200-with-`errors` never emits; rate-limit is
  HTTP 400 + `RATELIMITED`). Third local transport mirror (GraphQL, routed on
  operation+variables). Recorded responses under `fixtures/recorded/linear/`. See
  ADR-0017 Addendum 2026-06-23 (Linear).
- `screening.py` — `screen_descriptor` / `screen_item`: fail-closed reuse of the
  single `adapter.core.sensitive` catalog before any object crosses the boundary
  (ADR-0017 §3; shared by the GitHub + Drive + Linear slices).

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
│   ├── items/                        # Golden ProviderItemEnvelope examples
│   │   ├── linear-*.json
│   │   └── github-*.json
│   └── recorded/github/              # Recorded GitHub REST responses (#180)
├── github/                           # GitHubDiscoveryConnector (#180)
│   ├── auth.py · transport.py · mapping.py · connector.py
│   └── tests/test_github_discovery.py
├── screening.py                      # Fail-closed descriptor/item screen
├── stub.py                           # FixtureDiscoveryStub (#178)
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
