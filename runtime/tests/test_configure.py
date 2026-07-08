# SPDX-License-Identifier: MIT
"""Behavior tests for the config-on-rails walk (#227; FX-RUNTIME-007).

Scripted IO seams drive the full Linear + Google Drive walks against recorded transports â€”
no live network, no real secret (a mock does NOT promote to Live â€” ADR-0012). Asserts the
acceptance criteria: mode-scoped credential collection, validation re-prompt, config round-trip,
env-mask warning, verify pass/fail, and the durable-OAuth refresh-triple persistence.
"""

from __future__ import annotations

import json
import threading
import urllib.parse
import urllib.request

from runtime.cli import main, run_connector
from runtime.configure import ConfigureIO, run_configure
from runtime.local_config import load_config
from runtime.poll_auth import PollError
from runtime.poll_client import HttpResponse


class _ScriptedIO(ConfigureIO):
    """ConfigureIO whose input/getpass pop from scripted queues; open_url records."""

    def __init__(self, inputs: list[str], secrets: list[str]) -> None:
        self._inputs = list(inputs)
        self._secrets = list(secrets)
        self.opened: list[str] = []
        super().__init__(
            input_fn=lambda prompt: self._inputs.pop(0) if self._inputs else "",
            getpass_fn=lambda prompt: self._secrets.pop(0),
            open_url_fn=self.opened.append,
        )


class _RecordingTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple] = []

    def request(self, method, url, *, headers, body=None):
        self.requests.append((method, url, headers, body))
        return self._responses.pop(0)


def _gql_page(n: int = 1) -> HttpResponse:
    nodes = [{"identifier": f"ENG-{i}", "title": "Fix bug", "description": "clean",
              "url": f"https://linear.app/x/ENG-{i}", "updatedAt": "2026-07-01",
              "state": {"name": "Open"}} for i in range(n)]
    body = {"data": {"issues": {"nodes": nodes,
                                "pageInfo": {"hasNextPage": False, "endCursor": None}}}}
    return HttpResponse(200, json.dumps(body).encode("utf-8"))


_DOC_ID = "1AbcDEF_ghi-jklMNOpqrstuvWXYZ0123456789"


def _doc_response() -> HttpResponse:
    doc = {"documentId": _DOC_ID, "title": "Q3 Plan", "body": {"content": [
        {"paragraph": {"elements": [{"textRun": {"content": "Hello world\n"}}],
                       "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}}}]}}
    return HttpResponse(200, json.dumps(doc).encode("utf-8"))


def test_linear_full_walk_stores_both_credentials(tmp_path):
    p = tmp_path / "bicameral.local.json"
    io = _ScriptedIO(inputs=["", "https://ops.example/hook", ""],  # Enter, receiver URL, spare
                     secrets=["lin_api_abc123", "whsec_shhh"])
    rc = run_configure("linear", str(p), io=io, transport=_RecordingTransport([_gql_page()]),
                       verify_fn=run_connector)
    assert rc == 0
    cfg = load_config(p)
    block = cfg.connectors["linear"]
    assert block["secrets"]["linear"] == "lin_api_abc123"
    assert block["secrets"]["linear_webhook"] == "whsec_shhh"
    assert block["enabled"] is True


def test_validation_regex_rejects_and_reprompts(tmp_path):
    p = tmp_path / "bicameral.local.json"
    io = _ScriptedIO(inputs=["", "https://ops.example/hook", ""],
                     secrets=["Bearer lin_api_abc123", "lin_api_ok9", "whsec_x"])
    rc = run_configure("linear", str(p), io=io, transport=_RecordingTransport([_gql_page()]),
                       verify_fn=run_connector)
    assert rc == 0
    assert load_config(p).connectors["linear"]["secrets"]["linear"] == "lin_api_ok9"


def test_mode_scoped_walk_skips_webhook_credential(tmp_path, capsys):
    p = tmp_path / "bicameral.local.json"
    io = _ScriptedIO(inputs=["", ""], secrets=["lin_api_only1"])
    rc = run_configure("linear", str(p), modes="active", io=io,
                       transport=_RecordingTransport([_gql_page()]), verify_fn=run_connector)
    assert rc == 0
    block = load_config(p).connectors["linear"]
    assert block["secrets"]["linear"] == "lin_api_only1"
    assert block["secrets"].get("linear_webhook", "") == ""  # never prompted (seed value only)
    assert io._secrets == []  # exactly one masked prompt consumed
    assert "skipping webhook registration" in capsys.readouterr().out


def test_unknown_connector_exits_2_token_free(tmp_path, capsys):
    rc = main(["--config", str(tmp_path / "x.json"), "configure", "nope"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "unknown connector" in err and "nope" in err


def test_env_mask_warning_names_key_only(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("BICAMERAL_LINEAR", "lin_api_envmask")
    p = tmp_path / "bicameral.local.json"
    io = _ScriptedIO(inputs=["", "https://ops.example/hook", ""],
                     secrets=["lin_api_filevalue", "whsec_x"])
    rc = run_configure("linear", str(p), io=io, transport=_RecordingTransport([_gql_page()]),
                       verify_fn=run_connector)
    assert rc == 0
    out = capsys.readouterr()
    assert "BICAMERAL_LINEAR" in out.err and "OVERRIDES" in out.err
    for stream in (out.out, out.err):  # key NAME only â€” never a value
        assert "lin_api_filevalue" not in stream and "lin_api_envmask" not in stream


def test_verify_failure_returns_1(tmp_path, capsys):
    p = tmp_path / "bicameral.local.json"

    def failing_verify(*args, **kwargs):
        raise PollError("poll:refused (status=401)")

    io = _ScriptedIO(inputs=["", "https://ops.example/hook", ""],
                     secrets=["lin_api_abc", "whsec_x"])
    rc = run_configure("linear", str(p), io=io, transport=_RecordingTransport([]),
                       verify_fn=failing_verify)
    assert rc == 1
    assert "verify FAILED" in capsys.readouterr().err
    assert load_config(p).connectors["linear"]["enabled"] is False  # persisted but NOT enabled


def test_google_drive_paste_token_path_warns_not_durable(tmp_path, capsys):
    p = tmp_path / "bicameral.local.json"
    io = _ScriptedIO(inputs=["", _DOC_ID, ""], secrets=["ya29.tok1h"])
    # inputs: blank document_id first (required -> re-prompt, audit #231 A2), then the real id
    io._inputs = ["", _DOC_ID, ""]
    rc = run_configure("google_drive", str(p), modes="active", io=io, paste_token=True,
                       transport=_RecordingTransport([_doc_response()]), verify_fn=run_connector)
    assert rc == 0
    out = capsys.readouterr().out
    assert "~1h" in out and "NOT durable" in out
    block = load_config(p).connectors["google_drive"]
    assert block["secrets"]["google_drive"] == "ya29.tok1h"
    assert block["runtime"]["document_id"] == _DOC_ID
    assert "ya29.tok1h" not in out  # masked input â€” never echoed


def _consenting_browser(io: _ScriptedIO):
    """open_url_fn that behaves like the operator granting consent: GET the redirect_uri with
    the state from the consent URL plus an auth code."""

    def opener(url: str) -> None:
        io.opened.append(url)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        redirect = q["redirect_uri"][0]
        state = q["state"][0]
        target = f"{redirect}?state={urllib.parse.quote(state)}&code=4/authcode-x"

        threading.Thread(target=lambda: urllib.request.urlopen(target, timeout=10),
                         daemon=True).start()

    return opener


def test_google_drive_oauth_consent_walk_persists_refresh_triple(tmp_path, capsys):
    p = tmp_path / "bicameral.local.json"
    io = _ScriptedIO(inputs=["client-id-123", _DOC_ID, ""], secrets=["client-secret-shh"])
    io.open_url_fn = _consenting_browser(io)
    transport = _RecordingTransport([
        HttpResponse(200, json.dumps({"refresh_token": "1//refresh-durable"}).encode()),  # exchange
        HttpResponse(200, json.dumps({"access_token": "ya29.minted", "expires_in": 3600}).encode()),
        _doc_response(),  # verify: documents.get
    ])
    rc = run_configure("google_drive", str(p), modes="active", io=io, transport=transport,
                       verify_fn=run_connector)
    assert rc == 0
    secrets = load_config(p).connectors["google_drive"]["secrets"]
    assert secrets["google_drive_refresh_token"] == "1//refresh-durable"
    assert secrets["google_drive_client_id"] == "client-id-123"
    assert secrets["google_drive_client_secret"] == "client-secret-shh"
    assert secrets.get("google_drive", "") == ""  # NEVER the access token (durable path only)
    out = capsys.readouterr()
    for leaked in ("1//refresh-durable", "client-secret-shh", "ya29.minted", "4/authcode-x"):
        assert leaked not in out.out and leaked not in out.err
    method, url, headers, body = transport.requests[-1]
    assert method == "GET" and url.endswith(_DOC_ID)
    assert headers["Authorization"] == "Bearer ya29.minted"  # minted from the persisted triple


def test_configure_subcommand_parses_without_existing_config(tmp_path, capsys):
    # dispatch reaches configure BEFORE load_config: a missing file is not an error path here
    rc = main(["--config", str(tmp_path / "absent.json"), "configure", "nope"])
    assert rc == 2  # fails on the unknown connector, NOT on "config not found"
    assert "config not found" not in capsys.readouterr().err


# --- review F1/F2/F3 regressions (implementation-review findings, 2026-07-08) ---

def test_consent_failure_exits_2_via_main(tmp_path, capsys, monkeypatch):
    # F1: a ConsentError surfaces as the one-line token-free exit-2 path, never a traceback.
    from runtime.oauth_consent import ConsentError

    def exploding_consent(**kwargs):
        raise ConsentError(0, "redirect_timeout")

    monkeypatch.setattr("runtime.configure.run_consent", exploding_consent)
    monkeypatch.setattr("builtins.input", lambda prompt="": "client-id")
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "cs-shh")
    rc = main(["--config", str(tmp_path / "c.json"), "configure", "google_drive",
               "--modes", "active"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "oauth_consent:redirect_timeout" in err and "cs-shh" not in err


def test_zendesk_active_walk_never_binds_webhook_paste_to_api_key(tmp_path, capsys):
    # F2: zendesk declares the webhook credential FIRST; in --modes active the adjacent
    # paste_secret must be SKIPPED, not re-bound to the api_key credential.
    p = tmp_path / "bicameral.local.json"
    io = _ScriptedIO(inputs=[""] * 8, secrets=["whsec_pasted_by_mistake"] * 4)
    rc = run_configure("zendesk", str(p), modes="active", io=io,
                       transport=_RecordingTransport([]), verify_fn=None)
    assert rc == 0
    block = load_config(p).connectors.get("zendesk", {})
    assert "whsec_pasted_by_mistake" not in (block.get("secrets") or {}).values()


def test_dual_mode_connector_without_runner_verify_prints_guidance(tmp_path, capsys):
    # F3: a declared-active connector with no CLI runner (zendesk) must not fail verify â€”
    # the cli edge passes verify_fn=None and the walk prints receiver-side guidance.
    p = tmp_path / "bicameral.local.json"
    io = _ScriptedIO(inputs=[""] * 8, secrets=["ztok"] * 4)
    rc = run_configure("zendesk", str(p), io=io, transport=_RecordingTransport([]),
                       verify_fn=None)
    assert rc == 0
    assert "active verify not available" in capsys.readouterr().out
    assert load_config(p).connectors["zendesk"]["enabled"] is True


def test_cli_edge_passes_no_verify_fn_for_unrunnable_connector():
    # F3: the cli edge itself makes the runnable decision (zendesk not in RUNNERS).
    from runtime.runner_registry import RUNNERS
    assert "zendesk" not in RUNNERS and "linear" in RUNNERS  # pins the premise


def test_linear_verify_actually_runs(tmp_path, capsys):
    # F6: the pass path proves run_connector executed (transport consumed + PASSED printed).
    p = tmp_path / "bicameral.local.json"
    io = _ScriptedIO(inputs=["", "https://ops.example/hook", ""],
                     secrets=["lin_api_abc123", "whsec_x"])
    transport = _RecordingTransport([_gql_page()])
    rc = run_configure("linear", str(p), io=io, transport=transport, verify_fn=run_connector)
    assert rc == 0
    assert transport.requests, "verify must actually drive the transport"
    assert "verify PASSED: 1 emission(s)" in capsys.readouterr().out


def test_configure_action_reprompts_on_non_numeric_int(tmp_path, monkeypatch):
    # F8: an int-typed runtime key re-prompts on non-numeric input instead of crashing.
    from runtime.configure import _Walk, _do_configure, ConfigureIO
    desc = {"id": "linear", "runtime_config": [
        {"key": "page_size", "label": "Page size", "required": False, "default": 50}]}
    inputs = iter(["fifty", "25"])
    walk = _Walk(connector_id="linear", desc=desc, config_path=str(tmp_path / "c.json"),
                 io=ConfigureIO(input_fn=lambda p: next(inputs), getpass_fn=lambda p: "",
                                open_url_fn=lambda u: None),
                 transport=_RecordingTransport([]), verify_fn=None, modes={"active"},
                 paste_token=False)
    _do_configure(walk, {"action": "configure", "text": ""})
    assert walk.runtime["page_size"] == 25
