# SPDX-License-Identifier: MIT
"""Behavior tests for the headless runner CLI (FX-RUNTIME-004; ADR-0016).

All driven through a RecordedTransport — no live network, no real secret (a mock does NOT promote
to Live, ADR-0012). Includes the security backstops: no secret in stdout, gateway gated, and the
gitignore-glob + tracked-config secret-shape scans.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from runtime.cli import _print_emissions, run_connector, run_mods
from runtime.local_config import ConfigError, LocalConfig
from runtime.poll_client import HttpResponse
from runtime.sinks import CollectingSink, GatewayEmissionGated, GatewaySink

_REPO = Path(__file__).resolve().parents[2]


class _RecordingTransport:
    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self._i = 0
        self.bodies: list = []

    def request(self, method, url, *, headers, body=None):
        self.bodies.append(body)
        resp = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return resp


def _gql_page(nodes, *, has_next, end_cursor) -> HttpResponse:
    body = {"data": {"issues": {"nodes": nodes, "pageInfo": {"hasNextPage": has_next, "endCursor": end_cursor}}}}
    return HttpResponse(200, json.dumps(body).encode("utf-8"))


def _issue(identifier, desc="a clean description") -> dict:
    return {"identifier": identifier, "title": "Fix bug", "description": desc,
            "url": f"https://linear.app/x/{identifier}", "updatedAt": "2026-06-01", "state": {"name": "Open"}}


def _linear_config(secret="lin_key_xyz") -> LocalConfig:
    return LocalConfig(
        connectors={"linear": {"enabled": True, "secrets": {"linear": secret, "linear_webhook": "whx"},
                               "runtime": {"page_size": 50}}},
        mods={"dependency_risk": {"enabled": True}}, gateway={}, secret_map={"linear": secret, "linear_webhook": "whx"},
    )


def test_run_connector_emits():
    transport = _RecordingTransport([
        _gql_page([_issue("ENG-1")], has_next=True, end_cursor="c1"),
        _gql_page([_issue("ENG-2")], has_next=False, end_cursor=None),
    ])
    sink = CollectingSink()
    assert run_connector("linear", _linear_config(), transport, sink) == 2


def test_unknown_connector_fails_closed():
    with pytest.raises(ConfigError) as exc:
        run_connector("nope", _linear_config(), _RecordingTransport([]), CollectingSink())
    assert "unknown or not-runnable" in str(exc.value)


def test_run_google_drive_requires_document_id():
    cfg = LocalConfig(connectors={"google_drive": {"enabled": True, "secrets": {"google_drive": "tok"}}},
                      mods={}, gateway={}, secret_map={"google_drive": "tok"})
    with pytest.raises(ConfigError) as exc:
        run_connector("google_drive", cfg, _RecordingTransport([]), CollectingSink())
    assert "document-id" in str(exc.value)


def test_limit_truncates():
    transport = _RecordingTransport([
        _gql_page([_issue("ENG-1")], has_next=True, end_cursor="c1"),
        _gql_page([_issue("ENG-2")], has_next=False, end_cursor=None),
    ])
    sink = CollectingSink()
    assert run_connector("linear", _linear_config(), transport, sink, limit=1) == 1
    assert len(sink.emissions) == 1


def test_gateway_sink_gated():
    sink = GatewaySink(endpoint="", token="")  # unconfigured -> emit raises
    transport = _RecordingTransport([_gql_page([_issue("ENG-1")], has_next=False, end_cursor=None)])
    with pytest.raises(GatewayEmissionGated):
        run_connector("linear", _linear_config(), transport, sink)


def test_run_mods_pipes_through_dependency_risk():
    # an issue whose description names a dependency manifest -> dependency_risk emits a dependency_signal.
    transport = _RecordingTransport([
        _gql_page([_issue("ENG-9", desc="bump deps in requirements.txt")], has_next=False, end_cursor=None),
    ])
    results = run_mods("linear", _linear_config(), transport, ["dependency_risk"])
    kinds = [e.output_type for e in results["dependency_risk"]]
    assert "dependency_signal" in kinds


def test_no_secret_in_stdout(capsys):
    secret = "lin_SUPERSECRET_value"
    transport = _RecordingTransport([_gql_page([_issue("ENG-1")], has_next=False, end_cursor=None)])
    sink = CollectingSink()
    run_connector("linear", _linear_config(secret=secret), transport, sink)
    _print_emissions(sink)
    assert secret not in capsys.readouterr().out  # screened emissions only — never the secret


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=_REPO, capture_output=True, text=True)


def test_local_config_gitignored():
    # B2: the glob ignores the canonical name AND siblings/variants; the example stays tracked.
    for ignored in ("config/bicameral.local.json", "config/bicameral.local.prod.json", "config/secrets.json"):
        assert _git("check-ignore", ignored).returncode == 0, ignored
    assert _git("check-ignore", "config/bicameral.example.json").returncode != 0  # NOT ignored


def test_no_secret_shapes_in_tracked_config():
    # B2: no real-secret-shaped value in any TRACKED config/*.json (independent of TruffleHog --only-verified).
    shapes = [r"lin_api_[A-Za-z0-9]{10,}", r"ya29\.[A-Za-z0-9_-]{10,}", r"\bAKIA[0-9A-Z]{16}\b",
              r"whsec_[A-Za-z0-9]{10,}", r"eyJ[A-Za-z0-9_-]+\.eyJ", r"Bearer [A-Za-z0-9._-]{12,}"]
    tracked = _git("ls-files", "config/*.json").stdout.split()
    for rel in tracked:
        text = (_REPO / rel).read_text(encoding="utf-8")
        for shape in shapes:
            assert not re.search(shape, text), f"{rel} matches secret shape {shape}"


def test_run_connector_active_needs_only_active_credential():
    # FX-RUNTIME-005: an active run no longer demands linear_webhook (modes=["webhook"]).
    cfg = LocalConfig(connectors={"linear": {"enabled": True, "secrets": {"linear": "lin_key"}, "runtime": {}}},
                      mods={}, gateway={}, secret_map={"linear": "lin_key"})
    transport = _RecordingTransport([_gql_page([_issue("ENG-1")], has_next=False, end_cursor=None)])
    assert run_connector("linear", cfg, transport, CollectingSink()) == 1
