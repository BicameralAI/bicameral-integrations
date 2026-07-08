# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""GraphQL transport seam for Linear discovery (mocked/recorded; live deferred).

The **third** transport variant in the discovery surface: Linear is a single GraphQL
POST endpoint (`https://api.linear.app/graphql`) with a `{query, variables}` body, so
this seam routes on **operation name + variables** rather than a REST path (GitHub
#180 / Drive #179 are REST). A local mirror — the three seams are provider-shaped, so
unification stays deferred; **no edit to #178/#179/#180 code**.

Layering: provider-acquisition (contract) layer only — no ``protocol → runtime``
import. The live ``urllib`` POST is operator-run and out of scope this cycle.
"""

from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class LinearResponse:
    """A GraphQL transport result: HTTP ``status`` + parsed ``data`` + ``errors``.

    Linear can return **HTTP 200 with a non-empty ``errors`` array** (must not be
    treated as success) and **rate-limits with HTTP 400 + ``errors[].code ==
    'RATELIMITED'``** — the connector's error mapping handles both.
    """

    status: int
    data: dict[str, Any] | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)


def route_key(operation: str, variables: dict[str, Any] | None) -> str:
    """Deterministic routing key: ``"<operation>[?sorted-encoded-variables]"``."""
    if not variables:
        return operation
    encoded = urllib.parse.urlencode(sorted((str(k), str(v)) for k, v in variables.items()))
    return f"{operation}?{encoded}"


@runtime_checkable
class LinearTransport(Protocol):
    """The GraphQL seam. A live ``urllib`` POST is the operator-run default (deferred);
    tests inject a :class:`RecordedTransport`."""

    def execute(
        self, *, operation: str, query: str, variables: dict[str, Any] | None = None
    ) -> LinearResponse: ...


class RecordedTransport:
    """Replays recorded Linear GraphQL responses keyed by :func:`route_key`.

    Routes load from a directory of recorded-response JSON files, each shaped
    ``{"operation", "variables"?, "status", "data"?, "errors"?}`` (underscore-prefixed
    keys are comments). An **unrouted** request returns a synthetic ``200`` with a
    ``NOT_FOUND`` GraphQL error so a missing recording fails closed.
    """

    def __init__(self, routes: dict[str, LinearResponse]) -> None:
        self._routes = dict(routes)

    @classmethod
    def from_dir(cls, directory: Path) -> RecordedTransport:
        routes: dict[str, LinearResponse] = {}
        for path in sorted(directory.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            rec = {k: v for k, v in raw.items() if not k.startswith("_")}
            key = route_key(str(rec["operation"]), rec.get("variables"))
            routes[key] = LinearResponse(
                status=int(rec["status"]),
                data=rec.get("data"),
                errors=list(rec.get("errors", [])),
            )
        return cls(routes)

    def execute(
        self, *, operation: str, query: str, variables: dict[str, Any] | None = None
    ) -> LinearResponse:
        return self._routes.get(
            route_key(operation, variables),
            LinearResponse(status=200, errors=[{"code": "ENTITY_NOT_FOUND"}]),
        )
