# GitHub Connector

The GitHub connector maps pull-request payloads into provider-neutral `Observation` objects for adapter normalization.

## Table of Contents

- [Status](#status)
- [Modes](#modes)
- [Public Surface](#public-surface)
- [Input and Output](#input-and-output)
- [Auth and Runtime Boundary](#auth-and-runtime-boundary)
- [Development](#development)
- [Related Documentation](#related-documentation)

## Status

Implemented:

- Pull-request payload parsing.
- Source reference generation from repository full name and PR number.
- URL/source handling through `can_handle_ref`.
- End-to-end normalization coverage through adapter core.

Deferred:

- Live GitHub API fetch.
- GitHub webhook signature verification.
- Credential resolution.

## Modes

| Mode | Status | Notes |
| --- | --- | --- |
| Active | Declared, parse surface implemented | Runtime fetch is deferred; tests use fixture payloads. |
| Webhook | Declared, verification deferred | Payload parsing can be reused once webhook verification is added. |

## Public Surface

| Symbol | Purpose |
| --- | --- |
| [`parse_pull_request(payload)`](connector.py) | Maps a GitHub pull-request object to an `Observation`. |
| [`GitHubConnector`](connector.py) | Declares `source_id = "github"` and active/webhook capabilities. |
| `GitHubConnector.can_handle_ref(ref)` | Accepts GitHub source refs or refs with GitHub URLs. |
| `GitHubConnector.observations(payload)` | Returns one parsed observation for a PR payload. |

## Input and Output

Expected input is a GitHub pull-request JSON object shaped like [`fixtures/pr_merged.json`](fixtures/pr_merged.json).

The connector preserves:

- Repository and PR number as the source ref.
- `html_url` as the source URL.
- PR title as the observation title.
- PR body as the excerpt, falling back to title.
- PR author login and merge timestamp where present.

## Auth and Runtime Boundary

Credential keys are documented in [`auth.md`](auth.md). Credentials are stored and resolved by the operator runtime, not by this connector package.

The connector must not write decisions, persist credentials, call the gateway directly, or skip `adapter.core.normalize`.

## Development

```bash
pytest connectors/github/tests -q
```

## Related Documentation

- [Connectors](../README.md)
- [Adapter Core](../../adapter/core/README.md)
- [Feature Index](../../docs/FEATURE_INDEX.md)
