# SPDX-License-Identifier: MIT
"""Live GraphQL poll path for the operator-runtime boundary (ADR-0012).

The *fetch* half for a connector whose live source is a GraphQL API (Linear) — the
counterpart of the REST ``poll_client.poll`` for providers that don't fit the page-list
shape. It POSTs a cursor-paginated query, walks ``pageInfo`` Relay pagination, and hands
the parsed nodes to ``pipeline.normalize`` (which screens FX-SEC-001) → ``sink.emit``.

Why a separate module (not the sealed REST ``poll_client``): GraphQL diverges on three
axes — the pagination cursor rides in the request **body** (``variables.after``, not the
URL), a query can return **HTTP 200 with an ``errors`` array** (partial/failed → must not
emit), and rate-limiting is **HTTP 400 + ``errors[].code == "RATELIMITED"``** (not 429).
Stdlib-only (``urllib`` via the injected ``HttpTransport``); the real network call stays
operator-run — tests drive a recorded transport (a mock does NOT promote to Live, ADR-0012).

Trust posture: the operator secret is injected by ``poll_specs`` and never appears in an
error (the ``GatewaySink`` discipline). The **provider response is untrusted** — fail-closed
on every shape deviation, the body is capped before parse, the cursor is screened on read,
and pages are bounded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from adapter.core.observations import Observation
from adapter.core.pipeline import normalize

from .poll_auth import PollAuth, PollError, _reject_control_chars
from .poll_client import HttpTransport
from .sinks import EmissionSink
from .versioning import adapter_version_for

_MAX_RESPONSE = 8 * 1024 * 1024  # cap a hostile/huge provider body before parse (local; not poll_client's)
_MAX_TOTAL_BYTES = 64 * 1024 * 1024  # aggregate BYTE cap across all pages (#101-2; mirrors poll_client)
_MAX_PAGES = 100  # bound a runaway/cyclic pager (fail-safe)
_MAX_TOTAL_ITEMS = 50_000  # aggregate cap across all pages (purple-team DOS-1, 2026-06-11)


def _dig(obj: object, dotted: str) -> object:
    """Walk a dotted key path through nested dicts (`"data.issues.nodes"`); ``None`` if any
    segment is missing or non-dict. Intentionally duplicated from ``poll_client._dig`` to keep
    this module standalone (importing a private cross-module symbol is worse coupling) — change both."""
    cur = obj
    for seg in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(seg)
    return cur


@dataclass(frozen=True)
class GraphQLPollSpec:
    """A GraphQL poll target: endpoint + auth + the pinned query and where to read results.

    ``nodes_path``/``page_info_path`` are dotted paths into ``data`` (e.g. ``data.issues.nodes`` /
    ``data.issues.pageInfo``). ``parse`` maps one node dict to an ``Observation``."""

    endpoint: str
    auth: PollAuth
    query: str
    nodes_path: str
    page_info_path: str
    parse: Callable[[dict], Observation]
    page_size: int = 50


def _ratelimited(errors: object) -> bool:
    """True iff a GraphQL ``errors`` value is a list carrying a dict with ``code == "RATELIMITED"``."""
    if not isinstance(errors, list):
        return False
    return any(isinstance(e, dict) and e.get("code") == "RATELIMITED" for e in errors)


def _parse_body(body: bytes) -> dict:
    """Cap → JSON-parse → require a dict. Fail-closed (token-free) on every deviation."""
    if len(body) > _MAX_RESPONSE:
        raise PollError(0, "oversized_body")
    try:
        parsed = json.loads(body)
    except (ValueError, UnicodeDecodeError, RecursionError):  # deeply-nested body -> fail closed (PARSE-1)
        raise PollError(0, "unparseable_body") from None
    if not isinstance(parsed, dict):
        raise PollError(0, "non_object_body")
    return parsed


def _decode_page(status: int, body: bytes) -> dict:
    """One response → a clean GraphQL data dict, or fail closed. Handles 200, 200+errors,
    400+RATELIMITED (backpressure), and any other status — all defensively, no crash."""
    if status == 400:
        # 400 body is still untrusted: cap+parse defensively; RATELIMITED is backpressure.
        try:
            err_body = _parse_body(body)
        except PollError:
            raise PollError(400, "http_error") from None
        if _ratelimited(err_body.get("errors")):
            raise PollError(0, "rate_limited")
        raise PollError(400, "http_error")
    if status != 200:
        raise PollError(status, "http_error")
    parsed = _parse_body(body)
    if parsed.get("errors"):  # a 200 can carry GraphQL errors — never emit a partial result
        raise PollError(0, "graphql_errors")
    if not isinstance(parsed.get("data"), dict):  # a well-formed OK response always carries a `data` object
        raise PollError(0, "missing_data")
    return parsed


def _next_cursor(page: dict, page_info_path: str) -> str | None:
    """The endCursor to use for the next page, or ``None`` to stop. Fail-closed: stop unless
    ``hasNextPage`` is True AND ``endCursor`` is a non-empty str; screen it before reuse."""
    info = _dig(page, page_info_path)
    if not isinstance(info, dict) or info.get("hasNextPage") is not True:
        return None
    cursor = info.get("endCursor")
    if not isinstance(cursor, str) or not cursor:
        return None
    _reject_control_chars("graphql_cursor", cursor)
    return cursor


def poll_graphql(
    spec: GraphQLPollSpec,
    transport: HttpTransport,
    sink: EmissionSink,
    *,
    adapter_version: str | None = None,
) -> int:
    """Walk a GraphQL cursor-paginated query and emit; return the emission count. Fail-closed.

    ``adapter_version=None`` derives ``<source_id>/<version>`` from the connector descriptor
    (single source — ``runtime.versioning``) using the emitted observations' source_id.
    """
    headers = {**spec.auth.headers(), "Content-Type": "application/json"}
    observations: list[Observation] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()  # detect a repeating/cyclic cursor (A8) — don't re-fetch a page
    total_bytes = 0
    for _ in range(_MAX_PAGES):
        variables = {"first": spec.page_size, "after": cursor}
        body = json.dumps({"query": spec.query, "variables": variables}).encode("utf-8")
        response = transport.request("POST", spec.endpoint, headers=headers, body=body)
        total_bytes += len(response.body)
        if total_bytes > _MAX_TOTAL_BYTES:  # aggregate byte cap (#101-2: few-huge-items walk)
            raise PollError(0, "aggregate_bytes_exceeded")
        page = _decode_page(response.status, response.body)
        nodes = _dig(page, spec.nodes_path)
        if not isinstance(nodes, list):
            raise PollError(0, "nodes_not_a_list")
        new = [spec.parse(n) for n in nodes if isinstance(n, dict)]
        if len(observations) + len(new) > _MAX_TOTAL_ITEMS:  # aggregate cap (DOS-1)
            raise PollError(0, "aggregate_items_exceeded")
        observations.extend(new)
        cursor = _next_cursor(page, spec.page_info_path)
        if cursor is None:
            break
        if cursor in seen_cursors:  # provider returned a cursor we already followed → stop (A8)
            raise PollError(0, "circular_cursor")
        seen_cursors.add(cursor)
    if not observations:
        return 0
    av = adapter_version or adapter_version_for(observations[0].source_ref.source_id)
    emissions = normalize(observations, adapter_version=av)  # FX-SEC-001 screen here
    sink.emit(emissions)
    return len(emissions)


__all__ = ["GraphQLPollSpec", "poll_graphql"]
