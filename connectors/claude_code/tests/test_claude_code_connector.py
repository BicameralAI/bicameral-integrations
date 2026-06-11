# SPDX-License-Identifier: MIT
"""Behavior tests for the Claude Code connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.claude_code.connector import ClaudeCodeConnector, parse_session_line

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "session_lines.jsonl"


def _lines() -> list[dict]:
    return [json.loads(ln) for ln in _FIXTURE.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_fixture_loads():
    assert len(_lines()) == 5


def test_user_line_maps_prompt():
    obs = parse_session_line(_lines()[0])
    assert obs is not None
    assert obs.excerpt == "add a health-check endpoint to the api"
    assert obs.author == "user"
    assert obs.source_ref.source_id == "claude_code"
    assert obs.source_ref.ref == "11111111-1111-1111-1111-111111111111"
    assert obs.source_ref.kind == "user"
    assert obs.timestamp == "2026-06-04T00:00:01.000Z"


def test_assistant_line_includes_text_and_tool_use():
    obs = parse_session_line(_lines()[1])
    assert obs is not None
    assert "I'll add a GET /health route." in obs.excerpt
    assert "[tool_use:Edit]" in obs.excerpt
    assert obs.author == "claude"
    assert obs.metadata["model"] == "claude-demo"


def test_summary_line_uses_summary_text():
    obs = parse_session_line(_lines()[2])
    assert obs is not None and obs.excerpt == "Added /health endpoint to the demo API."


def test_meta_line_returns_none():
    assert parse_session_line(_lines()[3]) is None  # the "mode" meta line


def test_empty_content_assistant_floors_excerpt():
    obs = parse_session_line(_lines()[4])
    assert obs is not None
    assert obs.excerpt == "[claude_code:assistant] 33333333-3333-3333-3333-333333333333"


def test_unknown_type_and_non_dict_return_none():
    assert parse_session_line({"type": "file-history-snapshot"}) is None
    assert parse_session_line({}) is None  # no type -> "unknown" -> filtered
    assert parse_session_line("notadict") is None  # type: ignore[arg-type]


def test_wrong_typed_fields_do_not_crash():
    # message non-dict, blocks non-dict / non-str text, int timestamp -> floor, no leak.
    assert parse_session_line({"type": "user", "message": 123, "uuid": "u1"}).excerpt == "[claude_code:user] u1"
    weird = {"type": "assistant", "uuid": "u2", "message": {"content": [{"type": "text", "text": 7}, "notablock"]}}
    assert parse_session_line(weird).excerpt == "[claude_code:assistant] u2"
    int_ts = parse_session_line({"type": "user", "uuid": "u3", "timestamp": 1759035772297})
    assert int_ts.timestamp == ""  # epoch-ms int never leaks into the str timestamp


def test_deeply_nested_content_does_not_recurse_to_crash():
    # A hostile transcript with deeply-nested tool_result lists must floor, not RecursionError.
    inner: object = "x"
    for _ in range(600):
        inner = [inner]
    line = {"type": "user", "uuid": "deep", "message": {"content": [{"type": "tool_result", "content": inner}]}}
    obs = parse_session_line(line)
    assert obs is not None and obs.excerpt == "[claude_code:user] deep"


def test_observations_batch_drops_none_and_normalizes():
    out = normalize(
        ClaudeCodeConnector().observations({"lines": _lines()}),
        adapter_version="claude_code/0.1.0",
    )
    # 5 lines in, the "mode" meta line dropped -> 4 evidence emissions
    assert len(out) == 4
    assert all(isinstance(e, AdapterEmission) and e.source_id == "claude_code" for e in out)
    assert all(e.evidence[0].excerpt.strip() for e in out)


def test_single_line_payload():
    out = ClaudeCodeConnector().observations(_lines()[0])
    assert len(out) == 1 and out[0].source_ref.kind == "user"


def test_excerpt_is_redact_and_passed():
    # arbitrary transcript text is redact-and-passed (email/phone scrubbed before emit).
    line = {"type": "user", "uuid": "u9", "message": {"content": "ping me at dev@corp.com"}}
    obs = parse_session_line(line)
    assert obs is not None and "dev@corp.com" not in obs.excerpt


def test_cwd_home_prefix_scrubbed():
    # the OS username must not leak through cwd; the home prefix collapses to ~/.
    for raw, expect in [
        ("C:\\Users\\krkna\\proj", "~/proj"),
        ("/Users/alice/work/app", "~/work/app"),
        ("/home/bob/x", "~/x"),
        ("G:\\MythologIQ\\repo", "G:\\MythologIQ\\repo"),  # no Users segment -> unchanged
    ]:
        obs = parse_session_line({"type": "user", "uuid": "c1", "cwd": raw})
        assert obs is not None and obs.metadata["cwd"] == expect


def test_cwd_unc_wsl_export_home_scrubbed():
    # purple-team SG-2026-06-12-J: UNC / WSL / export-home layouts must also drop the username.
    for raw, expect in [
        (r"\\fileserver\Users\bob.jones\proj", "~/proj"),
        (r"\\wsl$\Ubuntu\home\alice\app", "~/app"),
        ("/export/home/carol/x", "~/x"),
    ]:
        obs = parse_session_line({"type": "user", "uuid": "c1", "cwd": raw})
        assert obs is not None and obs.metadata["cwd"] == expect


def test_email_shaped_uuid_elided_from_floor_and_ref():
    # purple-team pii_on_wire: a poisoned email-shaped uuid must not reach the un-redacted floor/ref.
    obs = parse_session_line({"type": "user", "uuid": "contact-jane@corp.com-id", "message": {"content": ""}})
    assert obs is not None
    assert "jane@corp.com" not in obs.excerpt and "jane@corp.com" not in obs.source_ref.ref
    assert "id-elided" in obs.excerpt and obs.source_ref.ref == "id-elided"
