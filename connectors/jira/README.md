# Jira Connector

The Jira connector package is the scaffold for Jira Cloud source integration. It currently documents auth expectations and repository boundaries; provider parsing and live Jira client behavior are not implemented in this package yet.

## Table of Contents

- [Status](#status)
- [Planned Modes](#planned-modes)
- [Current Surface](#current-surface)
- [Auth and Runtime Boundary](#auth-and-runtime-boundary)
- [Implementation Expectations](#implementation-expectations)
- [Related Documentation](#related-documentation)

## Status

Implemented:

- Connector package scaffold.
- Auth note for expected Jira Cloud secret keys.

Deferred:

- Jira issue/event parsing.
- Jira Cloud REST client.
- Webhook verification and event normalization.
- Dynamic webhook registration.
- Tests and fixtures.

## Planned Modes

| Mode | Status | Notes |
| --- | --- | --- |
| Active | Planned | REST fetch for issue refs is expected once implementation begins. |
| Webhook | Planned | Incoming issue events require verification and replay protection before parsing. |

## Current Surface

| Path | Purpose |
| --- | --- |
| [`auth.md`](auth.md) | Documents Jira Cloud API token, account email, and webhook secret expectations. |
| [`__init__.py`](__init__.py) | Package marker. |

No `connector.py` is present yet. Add it only with fixtures, tests, README updates, and feature-index updates in the same implementation cycle.

## Auth and Runtime Boundary

Recommended v0 auth is Jira Cloud API token plus account email using HTTP Basic auth. Expected secret keys are documented in [`auth.md`](auth.md).

Dynamic webhook registration requires OAuth or Connect auth and is deferred.

## Implementation Expectations

When Jira implementation begins, contributors must:

- Add representative fixtures before relying on live payload behavior.
- Map provider payloads into `adapter.core.Observation`.
- Preserve issue key, URL, author, timestamp, and excerpt evidence.
- Add parser and normalization tests under `connectors/jira/tests/`.
- Add webhook verification and dedup tests before enabling webhook mode.
- Keep live credential resolution and durable cursor state outside this package unless an architecture decision explicitly moves that boundary.

## Related Documentation

- [Connectors](../README.md)
- [Adapter Core](../../adapter/core/README.md)
- [Feature Index](../../docs/FEATURE_INDEX.md)
- [ADR-0006 Active, Passive, and Webhook Modes](../../docs/adr/0006-active-passive-webhook-modes.md)
