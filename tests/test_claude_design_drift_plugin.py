import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "claude-code" / "design-drift"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_design_drift_plugin_package_contract():
    manifest = _json(PLUGIN / ".claude-plugin" / "plugin.json")
    hooks = _json(PLUGIN / "hooks" / "hooks.json")
    compatibility = _json(PLUGIN / "compatibility.json")

    assert manifest["name"] == "bicameral-design-drift"
    assert manifest["version"] == compatibility["plugin"]["version"]
    assert hooks["modules"] == ["./register.js"]

    assert compatibility["host"] == {
        "kind": "claude-code",
        "minimum_version": "2.1.287",
        "tested_versions": [],
        "provider_docs_verified": "2026-10-03",
    }
    assert compatibility["transport"]["kind"] == "existing-mcp"
    assert compatibility["transport"]["server"] == "bicameral"
    assert compatibility["transport"]["tool"] == "bicameral.preflight"
    assert compatibility["transport"]["owns_server_registration"] is False
    assert compatibility["migration"]["legacy_claude_settings_planning_hook"] == (
        "remove-when-plugin-active"
    )
    assert compatibility["migration"]["legacy_claude_settings_session_start_hook"] == "retain"

    assert compatibility["authority"] == {
        "canonical_state_mutation": False,
        "tool_approval": False,
        "prompt_rewrite": False,
        "tool_rewrite": False,
        "autonomous_confirmation": False,
    }


def test_design_drift_mod_uses_narrow_declared_surface():
    register = (PLUGIN / "hooks" / "register.js").read_text(encoding="utf-8")
    drift = (PLUGIN / "hooks" / "drift.js").read_text(encoding="utf-8")
    source = register + "\n" + drift
    compatibility = _json(PLUGIN / "compatibility.json")

    required = {
        "session.start",
        "classic.PostToolUse",
        "command.run",
        "session.end",
    }
    assert set(compatibility["events"]) == required

    for forbidden in (
        "$.fs.",
        "$.process.",
        "$.http.",
        "$.env.",
        "$.settings.",
        "$.prompt.",
        "$.tool.register",
        "$.tool.call",
        "$.model.",
        "$.session.messages",
    ):
        assert forbidden not in source

    assert "$.mcp.call" in register
    assert "ExitPlanMode" in drift
    assert "tool_response" in drift
    assert ".plan" in drift
    assert "tool_use_id" in drift
    assert "transcript" not in drift.lower()
    assert "messages" not in drift.lower()


def test_design_drift_does_not_launder_unavailable_or_timeout_into_clean():
    drift = (PLUGIN / "hooks" / "drift.js").read_text(encoding="utf-8")

    assert "provider_unavailable" in drift
    assert "analysis provider unavailable" in drift
    assert "timed_out" in drift
    assert "analysis timed out" in drift
    assert "invalid_trace" in drift
    assert "analysis failed validation" in drift
    assert "no drift conclusion asserted" in drift
    assert "safe to proceed" not in drift.lower()
    assert "globally aligned" not in drift.lower()


def test_design_drift_discards_stale_generation_results():
    register = (PLUGIN / "hooks" / "register.js").read_text(encoding="utf-8")

    assert "activeBoundaryKey" in register
    assert "activeBoundaryKey === boundaryKey" in register
    assert "latestBoundary = null" in register
