import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DRIFT = ROOT / "plugins" / "claude-code" / "design-drift" / "hooks" / "drift.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is not available")


def _run_node(tmp_path: Path, assertions: str) -> None:
    module = tmp_path / "drift.mjs"
    module.write_text(DRIFT.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "check.mjs"
    script.write_text(
        "import * as drift from " + json.dumps(module.as_uri()) + ";\n" + assertions,
        encoding="utf-8",
    )
    result = subprocess.run(
        [NODE, str(script)],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_exact_plan_boundary_hash_and_tool_use_id_fallback(tmp_path: Path):
    _run_node(
        tmp_path,
        r"""
const parsed = await drift.planningBoundaryFromClassicPostToolUse({
  tool_name: 'ExitPlanMode',
  session_id: 'session-1',
  tool_use_id: 'tool-plan-1',
  tool_response: { plan: 'hello' },
});
if (!parsed.ok) throw new Error(JSON.stringify(parsed));
if (parsed.boundary.host_turn_id !== 'tool-plan-1') throw new Error('turn fallback');
if (parsed.boundary.plan_digest !== 'sha256:2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824') {
  throw new Error(parsed.boundary.plan_digest);
}
""",
    )


def test_missing_exact_plan_bytes_refuses_transcript_recovery(tmp_path: Path):
    _run_node(
        tmp_path,
        r"""
const parsed = await drift.planningBoundaryFromClassicPostToolUse({
  tool_name: 'ExitPlanMode',
  session_id: 'session-1',
  turn_id: 'turn-1',
  transcript: 'pretend plan',
  messages: [{ role: 'assistant', content: 'pretend plan' }],
  tool_response: {},
});
if (parsed.ok || parsed.reason !== 'missing_plan_bytes') throw new Error(JSON.stringify(parsed));
""",
    )


def test_result_mapping_keeps_contradiction_timeout_and_unknown_distinct(tmp_path: Path):
    _run_node(
        tmp_path,
        r"""
const boundary = { host_kind: 'claude_code', host_session_id: 's', host_turn_id: 't', plan_digest: 'sha256:x' };
const wrap = (managed) => ({ content: [{ type: 'text', text: JSON.stringify({ request_id: 'r', managed_preflight: managed }) }] });
const contradiction = drift.normalizeMcpResult(wrap({
  outcome: 'binding_validated', limitations: [], analysis: { status: 'completed', classes: ['proposed', 'contradiction'], limitations: [] }
}), boundary);
if (contradiction.state !== 'contradiction') throw new Error(JSON.stringify(contradiction));
const timedOut = drift.normalizeMcpResult(wrap({
  outcome: 'binding_validated', limitations: [], analysis: { status: 'timed_out', classes: ['timeout'], limitations: [{ code: 'analysis_timed_out' }] }
}), boundary);
if (timedOut.state !== 'timed_out') throw new Error(JSON.stringify(timedOut));
const unclassified = drift.normalizeMcpResult(wrap({
  outcome: 'binding_validated', limitations: [], analysis: { status: 'completed', classes: ['evidence', 'searched_scope'], limitations: [] }
}), boundary);
if (unclassified.state !== 'completed_unclassified') throw new Error(JSON.stringify(unclassified));
if (!drift.statusText(unclassified).includes('no drift conclusion asserted')) throw new Error(drift.statusText(unclassified));
""",
    )


def test_mcp_error_is_never_rendered_as_clean(tmp_path: Path):
    _run_node(
        tmp_path,
        r"""
const result = drift.normalizeMcpResult({ isError: true, content: [] }, { plan_digest: 'sha256:x' });
if (result.state !== 'mcp_error') throw new Error(JSON.stringify(result));
const text = drift.statusText(result).toLowerCase();
if (text.includes('clear') || text.includes('aligned') || text.includes('safe')) throw new Error(text);
""",
    )
