# SPDX-License-Identifier: MIT
"""Behavior tests for ``python -m runtime.cli configure`` (FX-RUNTIME-005/006; ADR-0016).

All flows are driven through a stubbed I/O seam (no TTY, browser, or live network) + a recording
transport (a mock does NOT promote to Live — ADR-0012). Covers the acceptance matrix: regex
validation rejection, mode-scoped credential selection, config round-trip, and an ``oauth_consent``
flow with a stubbed transport — plus the security backstop that no secret is ever echoed.
"""

from __future__ import annotations

import json

import pytest

from runtime.configure import ConfigureIO, Configurator
from runtime.local_config import ConfigError, load_config
from runtime.poll_client import HttpResponse

_DOC_ID = "1AbcDEF_ghi-jklMNOpqrstuvWXYZ0123456789"  # valid documents.get id grammar


class _RecordingTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self._responses = list(responses)
        self._i = 0
        self.calls: list[tuple] = []

    def request(self, method, url, *, headers, body=None):
        self.calls.append((method, url))
        resp = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return resp


class _StubIO:
    """Feeds queued visible/masked inputs and records every printed line."""

    def __init__(
        self, *, prompts=None, secrets=None, code=("auth-code", "http://127.0.0.1:0/")
    ) -> None:
        self._prompts = list(prompts or [])
        self._secrets = list(secrets or [])
        self.out_lines: list[str] = []
        self.opened: list[str] = []
        self.auth_urls: list[str] = []
        self._code = code

    def prompt(self, _msg: str) -> str:
        return self._prompts.pop(0)

    def secret_prompt(self, _msg: str) -> str:
        return self._secrets.pop(0)

    def out(self, msg: str) -> None:
        self.out_lines.append(msg)

    def open_browser(self, url: str) -> bool:
        self.opened.append(url)
        return True

    def catch_code(self, build_auth_url):
        self.auth_urls.append(build_auth_url(self._code[1]))
        return self._code

    @property
    def text(self) -> str:
        return "\n".join(self.out_lines)


def _gql_page(nodes, *, has_next=False, end_cursor=None) -> HttpResponse:
    body = {
        "data": {
            "issues": {
                "nodes": nodes,
                "pageInfo": {"hasNextPage": has_next, "endCursor": end_cursor},
            }
        }
    }
    return HttpResponse(200, json.dumps(body).encode("utf-8"))


def _issue(identifier="ENG-1") -> dict:
    return {
        "identifier": identifier,
        "title": "Fix bug",
        "description": "a clean description",
        "url": f"https://linear.app/x/{identifier}",
        "updatedAt": "2026-06-01",
        "state": {"name": "Open"},
    }


def _doc(text="Hello world") -> HttpResponse:
    payload = {
        "documentId": _DOC_ID,
        "title": "Q3 Plan",
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [{"textRun": {"content": text + "\n"}}],
                        "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                    }
                }
            ]
        },
    }
    return HttpResponse(200, json.dumps(payload).encode("utf-8"))


def _io(transport, **kwargs) -> ConfigureIO:
    stub = _StubIO(**kwargs)
    io = ConfigureIO(
        prompt=stub.prompt,
        secret_prompt=stub.secret_prompt,
        out=stub.out,
        open_browser=stub.open_browser,
        transport=transport,
        catch_code=stub.catch_code,
    )
    io.stub = stub  # type: ignore[attr-defined]  # test-only handle for assertions
    return io


# --- Linear: full walk + mode-appropriate storage + verify against a recorded transport ----------


def test_configure_linear_walks_both_credentials_and_verifies(tmp_path):
    path = tmp_path / "bicameral.local.json"
    transport = _RecordingTransport([_gql_page([_issue()])])
    io = _io(
        transport,
        prompts=["", "https://recv.example/hook"],
        secrets=["lin_api_ABC123", "whsec_topsecret"],
    )
    assert Configurator(io).configure("linear", path) == 0

    cfg = load_config(path)
    block = cfg.connectors["linear"]
    assert block["enabled"] is True
    assert block["secrets"] == {
        "linear": "lin_api_ABC123",
        "linear_webhook": "whsec_topsecret",
    }
    assert "verify: PASS" in io.stub.text  # type: ignore[attr-defined]
    # the receiver URL the operator pastes INTO Linear is surfaced back to them
    assert "https://recv.example/hook" in io.stub.text  # type: ignore[attr-defined]


# --- Regex validation: a Bearer-prefixed key is rejected; a valid key is stored -----------------


def test_paste_secret_regex_rejects_then_accepts(tmp_path):
    path = tmp_path / "c.json"
    transport = _RecordingTransport([_gql_page([_issue()])])
    io = _io(transport, prompts=[""], secrets=["Bearer lin_api_bad", "lin_api_good"])
    assert Configurator(io).configure("linear", path, modes=["active"]) == 0
    assert load_config(path).connectors["linear"]["secrets"] == {
        "linear": "lin_api_good"
    }
    assert "does not match" in io.stub.text  # type: ignore[attr-defined]
    assert "lin_api_bad" not in io.stub.text  # type: ignore[attr-defined]  # rejected value never echoed


def test_paste_secret_gives_up_after_three_bad_values(tmp_path):
    path = tmp_path / "c.json"
    io = _io(
        _RecordingTransport([_gql_page([])]),
        prompts=[""],
        secrets=["nope1", "nope2", "nope3"],
    )
    with pytest.raises(ConfigError) as exc:
        Configurator(io).configure("linear", path, modes=["active"])
    assert "linear" in str(exc.value)


# --- Mode-scoped credential selection (FX-RUNTIME-005) ------------------------------------------


def test_active_only_mode_skips_webhook_credential(tmp_path):
    path = tmp_path / "c.json"
    transport = _RecordingTransport([_gql_page([_issue()])])
    io = _io(transport, prompts=[""], secrets=["lin_api_ACTIVEONLY"])
    assert Configurator(io).configure("linear", path, modes=["active"]) == 0
    secrets = load_config(path).connectors["linear"]["secrets"]
    assert secrets == {
        "linear": "lin_api_ACTIVEONLY"
    }  # linear_webhook (modes=[webhook]) not prompted
    assert "skipped register_webhook" in io.stub.text  # type: ignore[attr-defined]


def test_unknown_mode_fails_closed(tmp_path):
    io = _io(_RecordingTransport([]))
    with pytest.raises(ConfigError) as exc:
        Configurator(io).configure("linear", tmp_path / "c.json", modes=["nonsense"])
    assert "unknown mode" in str(exc.value)


# --- Config round-trip: what configure writes is exactly what load_config reads back ------------


def test_config_round_trip(tmp_path):
    path = tmp_path / "c.json"
    io = _io(
        _RecordingTransport([_gql_page([_issue()])]),
        prompts=[""],
        secrets=["lin_api_RT"],
    )
    Configurator(io).configure("linear", path, modes=["active"])
    cfg = load_config(path)
    assert cfg.secret_map["linear"] == "lin_api_RT"
    # re-loading the written file is stable + valid JSON
    assert json.loads(path.read_text())["connectors"]["linear"]["enabled"] is True


# --- oauth_consent with a stubbed transport (Google Drive) --------------------------------------


def test_configure_google_drive_oauth_consent_stubbed(tmp_path):
    path = tmp_path / "c.json"
    transport = _RecordingTransport(
        [
            HttpResponse(
                200,
                json.dumps(
                    {
                        "access_token": "ya29.exchange",
                        "refresh_token": "1//refresh",
                        "expires_in": 3599,
                    }
                ).encode(),
            ),
            HttpResponse(
                200,
                json.dumps(
                    {"access_token": "ya29.minted", "expires_in": 3599}
                ).encode(),
            ),
            _doc(),  # verify: documents.get
        ]
    )
    io = _io(
        transport, prompts=["client-id-123", _DOC_ID], secrets=["client-secret-xyz"]
    )
    assert Configurator(io).configure("google_drive", path) == 0

    block = load_config(path).connectors["google_drive"]
    assert block["enabled"] is True
    assert (
        block["secrets"]["google_drive"] == "ya29.minted"
    )  # the refresh-minted access token
    assert block["runtime"]["document_id"] == _DOC_ID
    assert "verify: PASS" in io.stub.text  # type: ignore[attr-defined]
    # the ~1h access-token vs durable refresh-token distinction is made explicit
    text = io.stub.text  # type: ignore[attr-defined]
    assert "~1h" in text and "refresh token" in text.lower()
    # the consent URL requested a refresh token (offline access) for the declared scopes
    auth_url = io.stub.auth_urls[0]  # type: ignore[attr-defined]
    assert "access_type=offline" in auth_url and "documents.readonly" in auth_url


def test_configure_google_drive_paste_token_escape_hatch(tmp_path):
    path = tmp_path / "c.json"
    io = _io(_RecordingTransport([_doc()]), prompts=[_DOC_ID], secrets=["ya29.pasted"])
    assert Configurator(io).configure("google_drive", path, paste_token=True) == 0
    assert (
        load_config(path).connectors["google_drive"]["secrets"]["google_drive"]
        == "ya29.pasted"
    )
    assert "NOT durable" in io.stub.text  # type: ignore[attr-defined]


# --- Security + clean-error backstops -----------------------------------------------------------


def test_unknown_connector_clean_error(tmp_path):
    io = _io(_RecordingTransport([]))
    with pytest.raises(ConfigError) as exc:
        Configurator(io).configure("does_not_exist", tmp_path / "c.json")
    assert "unknown connector" in str(exc.value)


def test_secret_never_appears_in_output(tmp_path):
    path = tmp_path / "c.json"
    secret = "lin_api_ULTRASECRET"
    io = _io(
        _RecordingTransport([_gql_page([_issue()])]), prompts=[""], secrets=[secret]
    )
    Configurator(io).configure("linear", path, modes=["active"])
    assert secret not in io.stub.text  # type: ignore[attr-defined]  # only "value hidden" ever printed


def test_created_from_example_when_absent(tmp_path):
    path = tmp_path / "fresh.json"
    assert not path.exists()
    io = _io(
        _RecordingTransport([_gql_page([_issue()])]),
        prompts=[""],
        secrets=["lin_api_X"],
    )
    Configurator(io).configure("linear", path, modes=["active"])
    assert path.exists()
    assert "creating" in io.stub.text.lower()  # type: ignore[attr-defined]
