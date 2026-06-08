# SPDX-License-Identifier: MIT
"""Behavior tests for the live-poll client (the ingest *fetch* half; ADR-0012).

The poll path is proven end-to-end through a RecordedTransport over captured
provider-response fixtures — request shape + auth/version headers + pagination +
parse + emission — without any live network call (a mock does not promote a
connector to Live; ADR-0012). Reference connector: anthropic_admin (PII-free).
"""

from __future__ import annotations

import base64
import json
import urllib.parse
from collections.abc import Callable
from pathlib import Path

import pytest

from adapter.core.sensitive import detect_sensitive
from connectors.anthropic_admin.connector import AnthropicAdminConnector
from connectors.copilot.connector import CopilotConnector
from connectors.devin.connector import DevinConnector
from connectors.granola.connector import GranolaConnector
from connectors.cursor.connector import CursorConnector
from connectors.openai_admin.connector import OpenAIAdminConnector
from connectors.servicenow.connector import ServiceNowConnector
from runtime.poll_auth import ApiKeyHeaderAuth, BasicAuth, BearerAuth, PollError
from runtime.poll_client import (
    HttpResponse,
    _read_capped,
    poll,
)
from runtime.poll_specs import (
    build_anthropic_admin_spec,
    build_copilot_spec,
    build_cursor_spec,
    build_devin_spec,
    build_granola_spec,
    build_openai_admin_spec,
    build_servicenow_spec,
)
from runtime.secrets import MappingSecretResolver
from runtime.sinks import CollectingSink

_FIXTURES = Path(__file__).parent / "fixtures"
_SECRET = "sk-ant-admin-TESTKEY-not-real"


def _fixture_bytes(name: str) -> bytes:
    return (_FIXTURES / name).read_bytes()


def _resp(name: str) -> HttpResponse:
    return HttpResponse(200, _fixture_bytes(name))


class RecordedTransport:
    """Returns queued responses in order; records every request for assertion."""

    def __init__(self, responses: list[HttpResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def request(self, method, url, *, headers, body=None) -> HttpResponse:
        self.requests.append((method, url, dict(headers), body))
        if not self._responses:
            raise AssertionError("RecordedTransport exhausted")
        return self._responses.pop(0)


def _spec(secret: str = _SECRET):
    resolver = MappingSecretResolver({"anthropic_admin": secret})
    return build_anthropic_admin_spec(resolver)


def test_anthropic_admin_poll_two_pages_emits_two() -> None:
    transport = RecordedTransport([_resp("anthropic_admin_usage_page1.json"),
                                   _resp("anthropic_admin_usage_page2.json")])
    sink = CollectingSink()
    count = poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=sink)
    assert count == 2
    assert len(sink.emissions) == 2
    # Both buckets parsed: page-1 input 1200+300+100=1600 / output 800; page-2 500 / 250.
    joined = " ".join(e.body for e in sink.emissions)
    assert "1600 input / 800 output" in joined
    assert "500 input / 250 output" in joined


def test_page_two_request_carries_returned_token_value() -> None:
    # Audit finding 4: prove token-DRIVEN advancement (page 2 carries page 1's
    # returned `next_page` VALUE), not merely that two responses drain.
    # NOTE: the param NAME ("page") is the UNVERIFIED A2 assumption — this proves
    # our machinery re-sends the provider's token, not that Anthropic accepts it.
    transport = RecordedTransport([_resp("anthropic_admin_usage_page1.json"),
                                   _resp("anthropic_admin_usage_page2.json")])
    poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=CollectingSink())
    assert len(transport.requests) == 2
    page2_url = transport.requests[1][1]
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(page2_url).query))
    assert query.get("page") == "pg2"  # the exact token page 1 returned


def test_request_shape_auth_and_version_headers() -> None:
    transport = RecordedTransport([_resp("anthropic_admin_usage_page1.json"),
                                   _resp("anthropic_admin_usage_page2.json")])
    poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=CollectingSink())
    method, url, headers, _ = transport.requests[0]
    assert method == "GET"
    assert headers["x-api-key"] == _SECRET
    assert headers["anthropic-version"] == "2023-06-01"
    assert "page" not in urllib.parse.urlsplit(url).query  # no token on page 1


def test_pagination_stops_on_has_more_false() -> None:
    transport = RecordedTransport([_resp("anthropic_admin_usage_page2.json")])  # has_more=false
    count = poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=CollectingSink())
    assert count == 1
    assert len(transport.requests) == 1


def test_has_more_true_but_no_token_stops_closed() -> None:
    body = json.dumps({"data": [], "has_more": True}).encode("utf-8")  # token absent
    transport = RecordedTransport([HttpResponse(200, body)])
    count = poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=CollectingSink())
    assert count == 0
    assert len(transport.requests) == 1  # fails closed: no second request, no loop


class _LoopingTransport:
    """Always claims another page (cyclic pager) to exercise the _MAX_PAGES cap."""

    def __init__(self) -> None:
        self.calls = 0

    def request(self, method, url, *, headers, body=None) -> HttpResponse:
        self.calls += 1
        page = {"data": [], "has_more": True, "next_page": f"t{self.calls}"}
        return HttpResponse(200, json.dumps(page).encode("utf-8"))


def test_max_pages_cap() -> None:
    transport = _LoopingTransport()
    with pytest.raises(PollError) as exc:
        poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=CollectingSink())
    assert exc.value.reason == "max_pages_exceeded"
    assert transport.calls <= 101  # bounded, not infinite


def test_poisoned_next_page_token_rejected() -> None:
    # Audit finding 6: the provider response is untrusted; a CR/LF in next_page
    # must not splice into the request URL.
    page = {"data": [], "has_more": True, "next_page": "pg2\r\nX-Injected: evil"}
    transport = RecordedTransport([HttpResponse(200, json.dumps(page).encode("utf-8"))])
    with pytest.raises(PollError) as exc:
        poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=CollectingSink())
    assert "page_token" in exc.value.reason


def test_blank_secret_fails_closed_no_request() -> None:
    transport = RecordedTransport([])
    with pytest.raises(PollError) as exc:
        # build raises before any poll/request is attempted
        spec = build_anthropic_admin_spec(MappingSecretResolver({}))
        poll(AnthropicAdminConnector(), spec, transport=transport, sink=CollectingSink())
    assert exc.value.reason == "secret_unresolved:anthropic_admin"
    assert transport.requests == []  # no request ever attempted


def test_non_200_raises_token_free() -> None:
    transport = RecordedTransport([HttpResponse(401, b'{"error":"unauthorized"}')])
    with pytest.raises(PollError) as exc:
        poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=CollectingSink())
    assert exc.value.status == 401
    assert _SECRET not in str(exc.value)  # token never in the error


def test_unparseable_page_body_fails_closed() -> None:
    bad = RecordedTransport([HttpResponse(200, b"<html>not json</html>")])
    with pytest.raises(PollError) as exc:
        poll(AnthropicAdminConnector(), _spec(), transport=bad, sink=CollectingSink())
    assert exc.value.reason == "unparseable_body"
    # items() yielding a non-list also fails closed
    nonlist = RecordedTransport([HttpResponse(200, json.dumps({"data": {"x": 1}}).encode())])
    with pytest.raises(PollError) as exc2:
        poll(AnthropicAdminConnector(), _spec(), transport=nonlist, sink=CollectingSink())
    assert exc2.value.reason == "items_not_a_list"


class _FakeFp:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, n: int) -> bytes:
        return self._data[:n]


def test_read_capped_bounds_response() -> None:
    out = _read_capped(_FakeFp(b"x" * 64), cap=16)
    assert len(out) == 16  # the cap bounds the read without a network call


def test_crlf_in_secret_rejected() -> None:
    with pytest.raises(PollError) as exc:
        ApiKeyHeaderAuth("x-api-key", "abc\r\ndef")
    assert "control_char" in exc.value.reason
    assert "abc" not in exc.value.reason  # value-free message


def test_recorded_response_is_pii_free() -> None:
    transport = RecordedTransport([_resp("anthropic_admin_usage_page1.json"),
                                   _resp("anthropic_admin_usage_page2.json")])
    sink = CollectingSink()
    poll(AnthropicAdminConnector(), _spec(), transport=transport, sink=sink)
    for emission in sink.emissions:
        assert detect_sensitive(emission.body) == []
        assert detect_sensitive(emission.title) == []


# --- Bearer fan-out: openai_admin / devin / copilot / granola --------------------

_BEARER = "bearer-token-not-real"


def _json_resp(payload) -> HttpResponse:
    return HttpResponse(200, json.dumps(payload).encode("utf-8"))


def test_bearer_auth_header_and_extra() -> None:
    auth = BearerAuth("tok", extra={"X-GitHub-Api-Version": "2022-11-28"})
    headers = auth.headers()
    assert headers["Authorization"] == "Bearer tok"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"
    with pytest.raises(PollError) as exc:
        BearerAuth("ab\r\ncd")
    assert "control_char" in exc.value.reason
    assert "ab" not in exc.value.reason  # value-free


def test_openai_admin_poll_two_pages_cursor() -> None:
    transport = RecordedTransport([_resp("openai_admin_audit_page1.json"),
                                   _resp("openai_admin_audit_page2.json")])
    resolver = MappingSecretResolver({"openai_admin": _BEARER})
    count = poll(OpenAIAdminConnector(), build_openai_admin_spec(resolver),
                 transport=transport, sink=CollectingSink())
    assert count == 2
    # request 1 is Bearer-authed and carries no cursor
    assert transport.requests[0][2]["Authorization"] == f"Bearer {_BEARER}"
    assert "after" not in urllib.parse.urlsplit(transport.requests[0][1]).query
    # request 2 carries the returned last_id ("evt_9") as `after` — token-DRIVEN advance
    q2 = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(transport.requests[1][1]).query))
    assert q2.get("after") == "evt_9"


def test_copilot_top_level_array_emits_per_day() -> None:
    # Proves the NEW top-level-array page path (a dict-only harness would reject it).
    transport = RecordedTransport([_resp("copilot_metrics.json")])
    resolver = MappingSecretResolver({"copilot": _BEARER})
    sink = CollectingSink()
    count = poll(CopilotConnector(), build_copilot_spec(resolver), transport=transport, sink=sink)
    assert count == 2  # two day objects in the top-level array
    assert len(transport.requests) == 1  # 2 < per_page(100) → short page, stops after one
    assert transport.requests[0][2]["X-GitHub-Api-Version"] == "2022-11-28"


def test_copilot_page_number_pagination() -> None:
    # page-number pager (page/per_page): a full page (==per_page) advances `page`; a short page stops.
    p1 = [{"date": "2026-06-01"}, {"date": "2026-06-02"}]  # == per_page(2) → advance
    p2 = [{"date": "2026-06-03"}]                            # < per_page → stop
    transport = RecordedTransport([_json_resp(p1), _json_resp(p2)])
    resolver = MappingSecretResolver({"copilot": _BEARER})
    count = poll(CopilotConnector(), build_copilot_spec(resolver, per_page=2),
                 transport=transport, sink=CollectingSink())
    assert count == 3
    assert len(transport.requests) == 2  # advanced once, then stopped on the short page
    q2 = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(transport.requests[1][1]).query))
    assert q2.get("page") == "2"  # 1-based page advanced


def test_devin_cursor_pagination() -> None:
    # verified contract: `items` envelope; cursor end_cursor/has_next_page re-sent as ?after=
    transport = RecordedTransport([_resp("devin_sessions.json"),
                                   _resp("devin_sessions_page2.json")])
    resolver = MappingSecretResolver({"devin": _BEARER})
    base = "https://api.devin.ai/v3/organizations/org_demo/sessions"  # operator-templated org
    sink = CollectingSink()
    count = poll(DevinConnector(), build_devin_spec(resolver, base_url=base),
                 transport=transport, sink=sink)
    assert count == 3  # 2 (page 1) + 1 (page 2)
    # page 2 carries the returned end_cursor as `after` (token-driven advance)
    q2 = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(transport.requests[1][1]).query))
    assert q2.get("after") == "cur2"
    # first pull_requests[].pr_url surfaced as the artifact url
    urls = [e.evidence[0].source_ref.url for e in sink.emissions]
    assert "https://github.com/example-org/shop/pull/412" in urls


def test_granola_notes_envelope() -> None:
    transport = RecordedTransport([_resp("granola_notes.json")])
    resolver = MappingSecretResolver({"granola": _BEARER})
    sink = CollectingSink()
    count = poll(GranolaConnector(), build_granola_spec(resolver), transport=transport, sink=sink)
    assert count == 1
    e = sink.emissions[0]
    assert "architecture sync" in e.title
    assert "poll-client fan-out" in e.body  # joined transcript[].text, not transcript_text
    assert e.evidence[0].author == "Reviewer A"  # first attendees[].name
    assert detect_sensitive(e.body) == []


def test_granola_cursor_pagination() -> None:
    # same-name cursor (next_param == token_field == "cursor") against a base that already
    # carries ?include=transcript: page 2 must carry the returned cursor AND keep `include`.
    p1 = {"notes": [{"id": "not_a", "title": "A", "transcript": [{"text": "x"}]}],
          "hasMore": True, "cursor": "cur_2"}
    p2 = {"notes": [{"id": "not_b", "title": "B", "transcript": [{"text": "y"}]}],
          "hasMore": False, "cursor": None}
    transport = RecordedTransport([_json_resp(p1), _json_resp(p2)])
    resolver = MappingSecretResolver({"granola": _BEARER})
    count = poll(GranolaConnector(), build_granola_spec(resolver), transport=transport, sink=CollectingSink())
    assert count == 2
    q2 = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(transport.requests[1][1]).query))
    assert q2.get("cursor") == "cur_2"  # token-driven advance, same-name param
    assert q2.get("include") == "transcript"  # base query string preserved


def test_wrong_envelope_key_emits_zero() -> None:
    # The envelope-key assumption's blast radius: a {data:[...]} body for devin/granola
    # (whose verified keys are items/notes) yields 0 emissions, no error.
    devin_resolver = MappingSecretResolver({"devin": _BEARER})
    t1 = RecordedTransport([_json_resp({"data": [{"session_id": "x"}]})])
    assert poll(DevinConnector(), build_devin_spec(devin_resolver, base_url="https://x/y"),
                transport=t1, sink=CollectingSink()) == 0
    granola_resolver = MappingSecretResolver({"granola": _BEARER})
    t2 = RecordedTransport([_json_resp({"data": [{"id": "x"}]})])
    assert poll(GranolaConnector(), build_granola_spec(granola_resolver),
                transport=t2, sink=CollectingSink()) == 0


def test_non_object_body_still_fails_closed() -> None:
    resolver = MappingSecretResolver({"granola": _BEARER})
    scalar = RecordedTransport([HttpResponse(200, b"42")])
    with pytest.raises(PollError) as exc:
        poll(GranolaConnector(), build_granola_spec(resolver), transport=scalar, sink=CollectingSink())
    assert exc.value.reason == "non_object_body"
    # a top-level array does NOT raise non_object_body (the positive path the rename exists for)
    arr = RecordedTransport([HttpResponse(200, b"[]")])
    assert poll(CopilotConnector(), build_copilot_spec(MappingSecretResolver({"copilot": _BEARER})),
                transport=arr, sink=CollectingSink()) == 0


def test_blank_secret_fails_closed_each_spec() -> None:
    empty = MappingSecretResolver({})  # keyed by source_id; all miss → ''
    builders: list[Callable[..., object]] = [
        build_openai_admin_spec, build_copilot_spec, build_granola_spec
    ]
    for build in builders:
        with pytest.raises(PollError) as exc:
            build(empty)
        assert exc.value.reason.startswith("secret_unresolved:")
    with pytest.raises(PollError):  # devin requires base_url
        build_devin_spec(empty, base_url="https://x/y")


# --- Basic-auth fan-out: cursor (POST body) / servicenow (offset pagination) ------


def test_basic_auth_header_and_extra() -> None:
    auth = BasicAuth("KEY", "", extra={"Content-Type": "application/json"})
    headers = auth.headers()
    assert headers["Authorization"] == "Basic " + base64.b64encode(b"KEY:").decode()
    assert headers["Content-Type"] == "application/json"
    with pytest.raises(PollError) as exc:  # raw username screened pre-base64
        BasicAuth("ab\r\ncd", "pw")
    assert "basic_username" in exc.value.reason
    assert "ab" not in exc.value.reason  # value-free
    with pytest.raises(PollError):  # password screened too
        BasicAuth("user", "pw\r\nx")


def test_cursor_post_body_and_basic_auth() -> None:
    transport = RecordedTransport([_resp("cursor_usage.json")])
    resolver = MappingSecretResolver({"cursor": "cursor-api-key"})
    body = {"startDate": "2026-06-01", "endDate": "2026-06-06"}  # unverified shape (caller-supplied)
    sink = CollectingSink()
    count = poll(CursorConnector(), build_cursor_spec(resolver, body=body), transport=transport, sink=sink)
    assert count == 2  # two daily-usage rows
    method, _url, headers, sent_body = transport.requests[0]
    assert method == "POST"
    assert headers["Authorization"] == "Basic " + base64.b64encode(b"cursor-api-key:").decode()
    assert headers["Content-Type"] == "application/json"
    assert sent_body == json.dumps(body).encode("utf-8")  # body plumbed through
    for emission in sink.emissions:  # PII-free (allowlist + opaque userId)
        assert detect_sensitive(emission.body) == []


def test_servicenow_offset_pagination() -> None:
    # limit=2: page 1 (2 records, full) advances sysparm_offset to 2; page 2 (1 record, short) stops.
    transport = RecordedTransport([_resp("servicenow_incidents_page1.json"),
                                   _resp("servicenow_incidents_page2.json")])
    resolver = MappingSecretResolver({"servicenow": "snow-password"})
    count = poll(ServiceNowConnector(),
                 build_servicenow_spec(resolver, instance="dev.example.service-now.com",
                                       username="svc_integration", limit=2),
                 transport=transport, sink=CollectingSink())
    assert count == 3
    assert len(transport.requests) == 2  # stopped on the short page; no third request
    q2 = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(transport.requests[1][1]).query))
    assert q2.get("sysparm_offset") == "2"  # advanced by exactly limit
    assert q2.get("sysparm_limit") == "2"   # carried from base_url, not re-set by the pager


def test_servicenow_offset_exact_multiple_edge() -> None:
    # Total is an exact multiple of limit: the final full page advances once more to a
    # 0-row page, which then stops cleanly (no crash, no infinite loop).
    full = {"result": [{"number": "INC1"}, {"number": "INC2"}]}  # 2 == limit
    empty: dict = {"result": []}
    transport = RecordedTransport([_json_resp(full), _json_resp(full), _json_resp(empty)])
    resolver = MappingSecretResolver({"servicenow": "snow-password"})
    count = poll(ServiceNowConnector(),
                 build_servicenow_spec(resolver, instance="x", username="u", limit=2),
                 transport=transport, sink=CollectingSink())
    assert count == 4  # 2 + 2 + 0
    assert len(transport.requests) == 3  # full, full, empty → stop


def test_servicenow_single_short_page_no_second_request() -> None:
    transport = RecordedTransport([_resp("servicenow_incidents_page2.json")])  # 1 record < limit 2
    resolver = MappingSecretResolver({"servicenow": "snow-password"})
    count = poll(ServiceNowConnector(),
                 build_servicenow_spec(resolver, instance="dev.example.service-now.com",
                                       username="svc_integration", limit=2),
                 transport=transport, sink=CollectingSink())
    assert count == 1
    assert len(transport.requests) == 1  # stop-on-short-page


def test_blank_secret_fails_closed_basic() -> None:
    empty = MappingSecretResolver({})  # keyed by source_id
    with pytest.raises(PollError) as e1:
        build_cursor_spec(empty, body={})
    assert e1.value.reason == "secret_unresolved:cursor"
    with pytest.raises(PollError) as e2:
        build_servicenow_spec(empty, instance="x", username="u")
    assert e2.value.reason == "secret_unresolved:servicenow"
