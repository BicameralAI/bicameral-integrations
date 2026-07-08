# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""Pinned Linear GraphQL operation strings (ADR-0017 alpha 3/3).

Relay pagination (`first`/`after`, `pageInfo{hasNextPage endCursor}`, `nodes`), the
same shape as the repo-verified ``runtime.poll_specs._LINEAR_ISSUES_QUERY``. Ids ride
in **variables** (JSON-encoded by the transport), never string-spliced into the query.
Operation names double as the recorded-transport routing keys.
"""

from __future__ import annotations

# Workspace (organization) + the teams under it — one round trip.
TEAMS = (
    "query Teams($first: Int!, $after: String) { "
    "organization { id name urlKey } "
    "teams(first: $first, after: $after) { "
    "nodes { id key name } pageInfo { hasNextPage endCursor } } }"
)

# Projects under a team (+ organization for the URI urlKey).
PROJECTS = (
    "query Projects($id: String!, $first: Int!, $after: String) { "
    "organization { urlKey } "
    "team(id: $id) { id key name "
    "projects(first: $first, after: $after) { "
    "nodes { id name } pageInfo { hasNextPage endCursor } } } }"
)

# Issues under a project (+ the parent team + organization for parent ref / URI).
ISSUES = (
    "query Issues($id: String!, $first: Int!, $after: String) { "
    "organization { urlKey } "
    "project(id: $id) { id name team { id key } "
    "issues(first: $first, after: $after) { "
    "nodes { id identifier title url updatedAt priority state { name } } "
    "pageInfo { hasNextPage endCursor } } } }"
)

# Single-node gets.
ORG = "query Org { organization { id name urlKey } }"
TEAM = "query Team($id: String!) { team(id: $id) { id key name organization { id name urlKey } } }"
PROJECT = (
    "query Project($id: String!) { organization { urlKey } "
    "project(id: $id) { id name team { id key } } }"
)
ISSUE = (
    "query Issue($id: String!) { issue(id: $id) { "
    "id identifier title description url updatedAt priority state { name } team { id key } } }"
)
COMMENT = (
    "query Comment($id: String!) { comment(id: $id) { "
    "id body createdAt issue { id identifier } } }"
)
