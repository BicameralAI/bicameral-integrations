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
        "thread_scope": "main-thread-only",
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
    assert compatibility["planning_boundary"]["subagent_event_behavior"] == (
        "ignore-without-state-mutation"
    )
    assert compatibility["product_routing"] == {
        "session_root_hint": "session.start.cwd",
        "later_cwd_updates": "ignored-for-product-routing",
        "cwd_is_product_identity": False,
        "resolver": "pending-bicameral.workspace.resolve-mcp-871",
        "selection": "existing-bicameral.product.select",
    }
    assert compatibility["response_integrity"] == {
        "max_content_items": 16,
        "max_total_json_chars": 262144,
        "max_candidates": 256,
        "conflicting_managed_preflight": "fail-closed",
        "conflicting_candidate_surface": "fail-closed",
        "success_error_mix": "fail-closed",
        "managed_enum_validation": "closed-current-bot-contract",
        "digest_format": "sha256-lowercase-64hex",
        "candidate_identity_format": "uuid",
        "raw_candidate_spec_limitation_prose_in_command_text": False,
    }


def test_design_drift_provider_documentation_contract():
    compatibility = _json(PLUGIN / "compatibility.json")
    documentation = compatibility["documentation"]
    references_path = PLUGIN / documentation["local_references"]
    provider_family_path = PLUGIN / documentation["provider_family"]
    category_contract_path = PLUGIN / documentation["category_contract"]
    repository_index_path = PLUGIN / documentation["repository_index"]

    assert references_path.is_file()
    assert provider_family_path.is_file()
    assert category_contract_path.is_file()
    assert repository_index_path.is_file()
    assert documentation["refresh_cadence"] == "monthly"
    assert documentation["source_precedence"] == "generated-types-then-official-provider-docs"
    assert documentation["generated_types_path"] == ".claude-plugin/types/"

    references = references_path.read_text(encoding="utf-8")
    for official_url in (
        "https://code.claude.com/docs/en/plugins/mods/overview",
        "https://code.claude.com/docs/en/plugins/mods/create",
        "https://code.claude.com/docs/en/plugins/mods/reference",
        "https://code.claude.com/docs/en/plugins/mods/api",
        "https://code.claude.com/docs/en/hooks",
        "https://code.claude.com/docs/en/plugins/manifest-reference",
        "https://code.claude.com/docs/en/plugins/install",
        "https://code.claude.com/docs/en/plugins/security",
        "https://code.claude.com/docs/en/plugins/mods/admin",
        "https://github.com/anthropics/claude-code/blob/main/mods/types/claude-code.d.ts",
        "https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md",
    ):
        assert official_url in references

    assert "Claude Agent SDK" in references
    assert "not a dependency or authority source" in references
    assert ".claude-plugin/types/" in references


def test_design_drift_mod_uses_narrow_declared_surface():
    register = (PLUGIN / "hooks" / "register.js").read_text(encoding="utf-8")
    drift = (PLUGIN / "hooks" / "drift.js").read_text(encoding="utf-8")
    integrity = (PLUGIN / "hooks" / "integrity.js").read_text(encoding="utf-8")
    provider = (PLUGIN / "hooks" / "provider.js").read_text(encoding="utf-8")
    source = "\n".join((register, drift, integrity, provider))
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


def test_design_drift_remediation_frame_is_enforced_in_source():
    register = (PLUGIN / "hooks" / "register.js").read_text(encoding="utf-8")
    provider = (PLUGIN / "hooks" / "provider.js").read_text(encoding="utf-8")
    integrity = (PLUGIN / "hooks" / "integrity.js").read_text(encoding="utf-8")

    assert "planningThreadDisposition" in register
    assert "subagent_boundary_ignored" in provider
    assert "agent_id" in provider
    assert "sessionRoutingHintFromStart" in register
    assert "session.start.cwd" in provider
    assert "scheduledKey" in register
    assert "normalizeBoundedMcpResult" in register
    assert "managed_preflight_conflict" in integrity
    assert "candidate_surface_conflict" in integrity
    assert "MAX_TOTAL_JSON_CHARS" in integrity
    assert "MANAGED_OUTCOMES" in integrity
    assert "SEMANTIC_CLASSES" in integrity
