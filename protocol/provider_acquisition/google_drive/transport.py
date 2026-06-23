# Copyright 2026 Bicameral AI — MIT License
"""Transport seam for Drive discovery (mocked/recorded; live deferred to factory#93).

A local mirror of #180's GitHub seam (the two were not unified — a shared `params`
Protocol would have changed GitHub's no-`params` shape and forced edits to merged
code; provider mechanics live with the provider, like ``mapping.py``). This seam
adds a ``params`` dict because Drive's `files.list`/`drives.list` carry rich query
parameters; routing keys are built deterministically from sorted params so recorded
fixtures declare params as a readable dict (no hand-URL-encoding).

Layering: provider-acquisition (contract) layer only — no ``protocol → runtime``
import. The live ``urllib`` transport is operator-run and out of scope this cycle.
"""

from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class DriveResponse:
    """A transport result: HTTP ``status`` + parsed ``json`` + ``headers``."""

    status: int
    json: Any = None
    headers: dict[str, str] = field(default_factory=dict)


def route_key(method: str, path: str, params: dict[str, Any] | None) -> str:
    """Deterministic routing key: ``"<METHOD> <path>[?sorted-encoded-params]"``."""
    base = f"{method.upper()} {path}"
    if not params:
        return base
    encoded = urllib.parse.urlencode(sorted((str(k), str(v)) for k, v in params.items()))
    return f"{base}?{encoded}"


@runtime_checkable
class DriveTransport(Protocol):
    """The network seam. A live ``urllib`` transport is the operator-run default
    (deferred to factory#93); tests inject a :class:`RecordedTransport`."""

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> DriveResponse: ...


class RecordedTransport:
    """Replays recorded Drive REST responses keyed by :func:`route_key`.

    Routes load from a directory of recorded-response JSON files, each shaped
    ``{"method", "path", "params"?, "status", "headers"?, "json"?}`` (underscore-
    prefixed keys are comments). An **unrouted** request returns a synthetic ``404``
    (→ ``NOT_FOUND``) so a missing recording fails closed rather than raising.
    """

    def __init__(self, routes: dict[str, DriveResponse]) -> None:
        self._routes = dict(routes)

    @classmethod
    def from_dir(cls, directory: Path) -> RecordedTransport:
        routes: dict[str, DriveResponse] = {}
        for path in sorted(directory.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            rec = {k: v for k, v in raw.items() if not k.startswith("_")}
            key = route_key(str(rec["method"]), str(rec["path"]), rec.get("params"))
            routes[key] = DriveResponse(
                status=int(rec["status"]),
                json=rec.get("json"),
                headers={str(k): str(v) for k, v in rec.get("headers", {}).items()},
            )
        return cls(routes)

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> DriveResponse:
        return self._routes.get(route_key(method, path, params), DriveResponse(status=404))
