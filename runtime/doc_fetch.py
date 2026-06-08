# SPDX-License-Identifier: MIT
"""Live single-document GET fetch path for the operator-runtime boundary (ADR-0012).

The *fetch* half for a connector whose live source is a single addressable resource fetched by
id (Google Docs ``documents.get``) — distinct from REST list-pagination (``poll_client``) and the
GraphQL cursor (``graphql_poll``): one GET → one object → one Observation. Stdlib-only; the real
network call stays operator-run (tests drive a recorded transport — a mock does NOT promote a
connector to Live, ADR-0012).

Trust posture: the operator token is injected by ``poll_specs`` and never appears in an error (the
``GatewaySink`` discipline). The provider response is **untrusted** — fail-closed on every shape
deviation, the body is capped before parse, and **only a JSON object** reaches the connector parse
(which is non-self-guarding, so this is its sole guard).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from adapter.core.observations import Observation
from adapter.core.pipeline import normalize

from .poll_auth import PollAuth, PollError
from .poll_client import HttpTransport
from .sinks import EmissionSink

_MAX_RESPONSE = 8 * 1024 * 1024  # cap a hostile/huge provider body before parse (local; not poll_client's)


@dataclass(frozen=True)
class DocFetchSpec:
    """A single-resource GET target: the resolved ``url`` + ``auth`` + a ``parse`` (dict→Observation)."""

    url: str
    auth: PollAuth
    parse: Callable[[dict], Observation]


def _decode(status: int, body: bytes) -> dict:
    """One response → a clean document dict, or fail closed (token-free). Dict-ONLY — the connector
    parse is non-self-guarding, so a non-dict 200 (list/scalar) must never reach it."""
    if status != 200:
        raise PollError(status, "http_error")
    if len(body) > _MAX_RESPONSE:  # the recorded transport does NOT cap — fetch_document owns this
        raise PollError(0, "oversized_body")
    try:
        parsed = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise PollError(0, "unparseable_body") from None
    if not isinstance(parsed, dict):
        raise PollError(0, "non_object_body")
    return parsed


def fetch_document(
    spec: DocFetchSpec,
    transport: HttpTransport,
    sink: EmissionSink,
    *,
    adapter_version: str = "runtime/0.1.0",
) -> int:
    """GET one document by its resolved URL, parse → screen → emit; return the count. Fail-closed."""
    response = transport.request("GET", spec.url, headers=spec.auth.headers())
    document = _decode(response.status, response.body)
    emissions = normalize([spec.parse(document)], adapter_version=adapter_version)  # FX-SEC-001 screen
    sink.emit(emissions)
    return len(emissions)


__all__ = ["DocFetchSpec", "fetch_document"]
