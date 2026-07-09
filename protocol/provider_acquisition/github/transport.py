# SPDX-License-Identifier: MIT
# Copyright 2026 Bicameral AI — MIT License
"""Transport seam for GitHub discovery (mocked/recorded; live deferred to cloud#7).

The connector issues logical GitHub REST requests through a ``GitHubTransport``.
The live ``urllib`` transport stays operator / hosted-side and is **out of scope**
this cycle (a mock never promotes to Live — ADR-0012). ``RecordedTransport``
replays recorded GitHub API responses from fixtures so the discovery path is proven
offline (the FX-RUNTIME-003 recorded-fixture pattern).

Layering: this seam lives in the provider-acquisition (contract) layer and does
**not** import the operator ``runtime`` package — it mirrors
``runtime.poll_client.HttpTransport``'s shape without coupling the two layers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class GitHubResponse:
    """A transport result: HTTP ``status`` + already-parsed ``json`` + ``headers``.

    The recorded transport hands back parsed JSON directly (the recordings are
    JSON); a live transport would ``json.loads`` the body before constructing this.
    """

    status: int
    json: Any = None
    headers: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class GitHubTransport(Protocol):
    """The network seam. A live ``urllib`` transport is the operator-run default
    (deferred to cloud#7); tests inject a :class:`RecordedTransport`."""

    def request(
        self, method: str, path: str, *, headers: dict[str, str]
    ) -> GitHubResponse: ...


class RecordedTransport:
    """Replays recorded GitHub REST responses keyed by ``"<METHOD> <path>"``.

    Routes load from a directory of recorded-response JSON files, each shaped
    ``{"method", "path", "status", "headers"?, "json"?}`` (underscore-prefixed
    keys are treated as comments and ignored). An **unrouted** request returns a
    synthetic ``404`` so a missing recording fails closed (the connector maps it
    to ``NOT_FOUND``) rather than raising.
    """

    def __init__(self, routes: dict[str, GitHubResponse]) -> None:
        self._routes = dict(routes)

    @classmethod
    def from_dir(cls, directory: Path) -> RecordedTransport:
        routes: dict[str, GitHubResponse] = {}
        for path in sorted(directory.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            rec = {k: v for k, v in raw.items() if not k.startswith("_")}
            key = f"{str(rec['method']).upper()} {rec['path']}"
            routes[key] = GitHubResponse(
                status=int(rec["status"]),
                json=rec.get("json"),
                headers={str(k): str(v) for k, v in rec.get("headers", {}).items()},
            )
        return cls(routes)

    def request(
        self, method: str, path: str, *, headers: dict[str, str]
    ) -> GitHubResponse:
        return self._routes.get(f"{method.upper()} {path}", GitHubResponse(status=404))
