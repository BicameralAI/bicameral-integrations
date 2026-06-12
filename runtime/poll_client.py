# SPDX-License-Identifier: MIT
"""Live-poll client for the operator-runtime boundary (ADR-0012).

The *fetch* half of a poll connector's ingest path — the symmetric counterpart of
``delivery.deliver_webhook``'s receive side. It constructs an authenticated
request, walks pagination, and hands the fetched payloads to
``delivery.deliver_poll`` (parse → normalize → emit). Stdlib-only (``urllib``,
like ``GatewaySink``); the real network call stays operator-run — tests drive it
through an injected ``HttpTransport`` over recorded fixtures (a mock does not
promote a connector to Live; ADR-0012).

Trust posture: the operator secret is injected by a ``SecretResolver`` and never
appears in an error or log (the ``GatewaySink`` discipline, red-team Cycle A #54).
The **provider response is untrusted** — the connector already treats
``observations()`` as an untrusted boundary; the pagination token is treated the
same (rejected if it carries control/space chars before being spliced into a URL).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Protocol, runtime_checkable

from .delivery import PollConnector, deliver_poll
from .poll_auth import PollAuth, PollError, _reject_control_chars
from .sinks import EmissionSink

_MAX_RESPONSE = 8 * 1024 * 1024  # cap a hostile/huge provider body before parse
_MAX_PAGES = 100  # cap a runaway/cyclic pager (fail-safe)
_MAX_TOTAL_ITEMS = 50_000  # aggregate cap across all pages: closes the per-page x _MAX_PAGES
#                            resident-memory multiplier (purple-team DOS-1, 2026-06-11)
_OK_STATUS = 200


class _NoFollowRedirect(urllib.request.HTTPRedirectHandler):
    """Never auto-follow a provider 3xx. The provider response is untrusted; following a
    redirect would re-send the operator credential (Authorization / x-api-key) to an
    attacker-chosen host (token exfiltration + SSRF) before the 200-only guard runs
    (purple-team SSRF-1, 2026-06-11). Returning None surfaces the 3xx as an HTTPError, which
    `UrllibTransport.request` maps to a non-200 HttpResponse -> fail-closed PollError."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


# Module-level no-follow opener (built once; stdlib HTTPRedirectHandler is otherwise default-on).
_NO_FOLLOW_OPENER = urllib.request.build_opener(_NoFollowRedirect).open


@dataclass(frozen=True)
class HttpResponse:
    """A transport result: HTTP ``status`` + raw ``body`` bytes."""

    status: int
    body: bytes


@runtime_checkable
class HttpTransport(Protocol):
    """The network seam. ``UrllibTransport`` is the operator-run default; tests
    inject a recorded transport so the poll path is proven without live network."""

    def request(
        self, method: str, url: str, *, headers: dict[str, str], body: bytes | None = None
    ) -> HttpResponse: ...


def _dig(obj: object, dotted: str) -> object:
    """Walk a dotted key path through nested dicts (`"metadata.nextCursor"`); ``None`` if
    any segment is missing or non-dict. A single segment (`"next_page"`) is a plain lookup."""
    cur = obj
    for seg in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(seg)
    return cur


@dataclass(frozen=True)
class PageToken:
    """Token / cursor pagination: the response carries a continuation token at
    ``token_field`` (a dotted path is allowed, e.g. ``metadata.nextCursor``), re-sent as
    query param ``next_param``. ``has_more_field`` gates advance when set (string path);
    when **``None``** there is no boolean has-more and advance stops purely on an
    absent/empty token (e.g. the MCP Registry). The param NAME/transport may be UNVERIFIED
    for some providers — see the connector's ``auth.md``. The provider token is untrusted:
    rejected on control chars, then URL-encoded.
    """

    next_param: str
    token_field: str = "next_page"
    has_more_field: str | None = "has_more"

    def next_url(self, current_url: str, page: object, item_count: int) -> str | None:
        if not isinstance(page, dict):  # a list/array page can't carry a token
            return None
        if self.has_more_field is not None and not _dig(page, self.has_more_field):
            return None
        token = _dig(page, self.token_field)
        if not isinstance(token, str) or not token:
            return None  # no usable token → stop closed, never loop
        _reject_control_chars("page_token", token)
        return _with_query_param(current_url, self.next_param, token)


@dataclass(frozen=True)
class OffsetPager:
    """Offset pagination: re-request with ``offset_param`` advanced by ``limit`` until a
    page returns fewer than ``limit`` items (no ``has_more``/token — e.g. ServiceNow's
    ``sysparm_offset``/``sysparm_limit``). Emits ONLY ``offset_param``; the page-size
    param (e.g. ``sysparm_limit``) lives in ``base_url`` and rides along in ``current_url``.
    """

    offset_param: str
    limit: int
    start: int = 0

    def next_url(self, current_url: str, page: object, item_count: int) -> str | None:
        if item_count < self.limit:
            return None  # short/empty page → last page; stop closed
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(current_url).query))
        try:
            offset = int(query.get(self.offset_param, self.start))
        except ValueError:
            offset = self.start  # defensive: a non-int offset never raises (fail-closed)
        return _with_query_param(current_url, self.offset_param, str(offset + self.limit))


@dataclass(frozen=True)
class PageNumberPager:
    """1-based page-number pagination: increment ``page_param`` until a page returns fewer
    than ``per_page`` items (no body cursor — e.g. GitHub Copilot metrics' ``page``/``per_page``).
    Keys off the extracted item count, so it works on a top-level-array OR enveloped response."""

    page_param: str
    per_page: int
    start: int = 1

    def next_url(self, current_url: str, page: object, item_count: int) -> str | None:
        if item_count < self.per_page:
            return None  # short page → last page; stop closed
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(current_url).query))
        try:
            current = int(query.get(self.page_param, self.start))
        except ValueError:
            current = self.start  # defensive: a non-int page never raises (fail-closed)
        return _with_query_param(current_url, self.page_param, str(current + 1))


@dataclass(frozen=True)
class PollSpec:
    """A connector's poll contract: where to fetch, how to authenticate, how to
    paginate, and how to extract the per-page payload list ``observations()`` eats."""

    base_url: str
    auth: PollAuth
    items: Callable[[Any], Any]
    method: str = "GET"
    pagination: PageToken | OffsetPager | PageNumberPager | None = None
    body: bytes | None = None


def _with_query_param(base_url: str, param: str, value: str) -> str:
    """Return ``base_url`` with ``param=value`` set in the query (value URL-encoded)."""
    parts = urllib.parse.urlsplit(base_url)
    query = dict(urllib.parse.parse_qsl(parts.query))
    query[param] = value
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def _read_capped(fp: Any, cap: int = _MAX_RESPONSE) -> bytes:
    """Read at most ``cap`` bytes from a file-like object (bounds a hostile body)."""
    return fp.read(cap)


class UrllibTransport:
    """Default transport over stdlib ``urllib`` (mirrors ``GatewaySink._post``).

    The operator runs the real network call; faults map to a token-free
    ``PollError``. A non-2xx response is returned (not raised) so the orchestrator
    handles status uniformly in one place.
    """

    def __init__(self, *, opener: Callable[..., Any] | None = None, timeout: float = 10.0) -> None:
        # No-follow opener by default: a provider 3xx must NOT auto-redirect a credentialed
        # request to a second host (SSRF-1). An operator who genuinely needs redirects passes
        # an explicit opener that strips auth headers + host-pins first.
        self._opener = opener or _NO_FOLLOW_OPENER
        self._timeout = timeout

    def request(
        self, method: str, url: str, *, headers: dict[str, str], body: bytes | None = None
    ) -> HttpResponse:
        req = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
        try:
            with self._opener(req, timeout=self._timeout) as response:
                status = getattr(response, "status", None) or response.getcode()
                return HttpResponse(status, _read_capped(response))
        except urllib.error.HTTPError as exc:  # 4xx/5xx — surface status + capped body
            return HttpResponse(exc.code, _read_capped(exc))
        except urllib.error.URLError as exc:  # transport fault — token-free detail
            raise PollError(0, f"transport_error:{type(exc.reason).__name__}") from None
        except Exception:  # never let an unexpected error carry request material
            raise PollError(0, "unexpected_error") from None


def _fetch_page(transport: HttpTransport, spec: PollSpec, url: str) -> object:
    """Fetch + parse one page; fail-closed on non-200 / unparseable / non-object body.

    A page is a JSON **object or array** (some providers, e.g. Copilot metrics, return
    a top-level array); a scalar/``null`` fails closed. ``spec.items`` unwraps it.
    """
    response = transport.request(spec.method, url, headers=spec.auth.headers(), body=spec.body)
    if response.status != _OK_STATUS:
        raise PollError(response.status, "unexpected_status_expected_200")
    try:
        parsed = json.loads(response.body)
    except (ValueError, UnicodeDecodeError, RecursionError):  # deeply-nested body -> fail closed (PARSE-1)
        raise PollError(0, "unparseable_body") from None
    if not isinstance(parsed, (dict, list)):
        raise PollError(0, "non_object_body")
    return parsed


def _items_of(spec: PollSpec, page: object) -> list:
    """Extract the per-page payload list, fail-closed if the extractor yields non-list."""
    items = spec.items(page)
    if not isinstance(items, list):
        raise PollError(0, "items_not_a_list")
    return items


def poll(
    connector: PollConnector,
    spec: PollSpec,
    *,
    transport: HttpTransport,
    sink: EmissionSink,
    adapter_version: str | None = None,
) -> int:
    """Fetch (with pagination) then ``deliver_poll`` (parse → normalize → emit).

    ``adapter_version=None`` lets ``deliver_poll`` derive ``<source_id>/<version>`` from the
    connector descriptor (single source — ``runtime.versioning``).

    Returns the emission count. Fail-closed: a non-200, an unparseable/non-object
    body, a non-list ``items`` result, a poisoned page token, or exceeding
    ``_MAX_PAGES`` all raise ``PollError``. The secret never appears in an error.
    """
    payloads: list = []
    url: str | None = spec.base_url
    pages = 0
    while url is not None:
        pages += 1
        if pages > _MAX_PAGES:
            raise PollError(0, "max_pages_exceeded")
        page = _fetch_page(transport, spec, url)
        items = _items_of(spec, page)
        if len(payloads) + len(items) > _MAX_TOTAL_ITEMS:  # aggregate cap (DOS-1)
            raise PollError(0, "aggregate_items_exceeded")
        payloads.extend(items)
        url = spec.pagination.next_url(url, page, len(items)) if spec.pagination else None
    return deliver_poll(connector, payloads, sink=sink, adapter_version=adapter_version)
