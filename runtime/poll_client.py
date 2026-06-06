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
from .secrets import SecretResolver
from .sinks import EmissionSink

_MAX_RESPONSE = 8 * 1024 * 1024  # cap a hostile/huge provider body before parse
_MAX_PAGES = 100  # cap a runaway/cyclic pager (fail-safe)
_OK_STATUS = 200


class PollError(RuntimeError):
    """A live poll failed. Carries ``status`` + ``reason``; the message never
    includes the operator secret/token (token-free, like ``GatewayEmissionError``)."""

    def __init__(self, status: int, reason: str = "") -> None:
        self.status = status
        self.reason = reason
        super().__init__(f"poll failed (status={status}, reason={reason or 'unknown'})")


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


@runtime_checkable
class PollAuth(Protocol):
    """Per-request auth headers. The operator runtime supplies the resolved secret."""

    def headers(self) -> dict[str, str]: ...


def _reject_control_chars(label: str, value: str) -> None:
    """Reject CR/LF + other control/space chars in a header or token value (a
    poisoned secret or provider token must not smuggle a header break / URL split)."""
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        raise PollError(0, f"{label}_contains_control_char")


class ApiKeyHeaderAuth:
    """API-key-in-header auth (e.g. Anthropic ``x-api-key`` + ``anthropic-version``).

    The only auth strategy shipped this cycle — Bearer/Basic land *with* their
    connectors (openai_admin/cursor/devin) rather than as untested orphans now.
    """

    def __init__(self, header: str, value: str, *, extra: dict[str, str] | None = None) -> None:
        self._headers = {header: value, **(extra or {})}
        for key, val in self._headers.items():
            _reject_control_chars(f"auth_header:{key}", val)

    def headers(self) -> dict[str, str]:
        return dict(self._headers)


@dataclass(frozen=True)
class PageToken:
    """Token pagination: response carries ``has_more_field`` (bool) + ``token_field``
    (a continuation token), re-sent as query param ``next_param``. The param NAME +
    transport may be UNVERIFIED — see the connector's ``auth.md`` (A2). The
    provider token is untrusted: rejected on control chars, then URL-encoded.
    """

    next_param: str
    token_field: str = "next_page"
    has_more_field: str = "has_more"

    def next_url(self, base_url: str, response_json: dict) -> str | None:
        if not response_json.get(self.has_more_field):
            return None
        token = response_json.get(self.token_field)
        if not isinstance(token, str) or not token:
            return None  # has_more true but no usable token → stop closed, never loop
        _reject_control_chars("page_token", token)
        return _with_query_param(base_url, self.next_param, token)


@dataclass(frozen=True)
class PollSpec:
    """A connector's poll contract: where to fetch, how to authenticate, how to
    paginate, and how to extract the per-page payload list ``observations()`` eats."""

    base_url: str
    auth: PollAuth
    items: Callable[[dict], Any]
    method: str = "GET"
    pagination: PageToken | None = None


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
        self._opener = opener or urllib.request.urlopen
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


def _fetch_page(transport: HttpTransport, spec: PollSpec, url: str) -> dict:
    """Fetch + parse one page; fail-closed on non-200 / unparseable / non-dict body."""
    response = transport.request(spec.method, url, headers=spec.auth.headers())
    if response.status != _OK_STATUS:
        raise PollError(response.status, "unexpected_status_expected_200")
    try:
        parsed = json.loads(response.body)
    except (ValueError, UnicodeDecodeError):
        raise PollError(0, "unparseable_body") from None
    if not isinstance(parsed, dict):
        raise PollError(0, "non_dict_body")
    return parsed


def _items_of(spec: PollSpec, page: dict) -> list:
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
    adapter_version: str = "runtime/0.1.0",
) -> int:
    """Fetch (with pagination) then ``deliver_poll`` (parse → normalize → emit).

    Returns the emission count. Fail-closed: a non-200, an unparseable/non-dict
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
        payloads.extend(_items_of(spec, page))
        url = spec.pagination.next_url(spec.base_url, page) if spec.pagination else None
    return deliver_poll(connector, payloads, sink=sink, adapter_version=adapter_version)


# Reference wiring: anthropic_admin (aggregate, PII-free). A1/A2 (UNVERIFIED):
# neither the top-level ``data`` envelope key nor the page-token param name/transport
# is in our verified contract (auth.md documents only "has_more + next_page"); both
# must be confirmed against live Anthropic docs before real-network wiring. Kept as
# config (a callable + an argument), not asserted as fact.
_ANTHROPIC_BASE = "https://api.anthropic.com/v1/organizations/usage_report/messages"
_ANTHROPIC_NEXT_PARAM = "page"  # A2 candidate — unverified


def build_anthropic_admin_spec(
    secret_resolver: SecretResolver,
    *,
    base_url: str = _ANTHROPIC_BASE,
    version: str = "2023-06-01",
    next_param: str = _ANTHROPIC_NEXT_PARAM,
) -> PollSpec:
    """Build the anthropic_admin poll spec (``x-api-key`` + ``anthropic-version``).

    Resolves the admin key via the injected resolver and raises a token-free
    ``PollError`` when blank — fail-closed, no request attempted.
    """
    secret = secret_resolver.resolve("anthropic_admin")
    if not secret:
        raise PollError(0, "secret_unresolved:anthropic_admin")
    auth = ApiKeyHeaderAuth("x-api-key", secret, extra={"anthropic-version": version})
    return PollSpec(
        base_url=base_url,
        auth=auth,
        items=lambda page: page.get("data", []),  # A1 envelope assumption (config, not fact)
        pagination=PageToken(next_param=next_param),
    )
