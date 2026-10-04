import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "plugins" / "claude-code" / "design-drift" / "hooks"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is not available")


def _run_routing(tmp_path: Path, assertions: str) -> None:
    drift = tmp_path / "drift.mjs"
    drift.write_text((HOOKS / "drift.js").read_text(encoding="utf-8"), encoding="utf-8")

    routing = tmp_path / "routing.mjs"
    routing.write_text(
        (HOOKS / "routing.js")
        .read_text(encoding="utf-8")
        .replace("'./drift.js'", "'./drift.mjs'"),
        encoding="utf-8",
    )

    script = tmp_path / "check.mjs"
    script.write_text(
        "import * as routing from " + json.dumps(routing.as_uri()) + ";\n" + assertions,
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


def test_route_uses_only_provider_hint_then_exact_daemon_product(tmp_path: Path):
    _run_routing(
        tmp_path,
        r"""
const calls = [];
const callTool = async (tool, args) => {
  calls.push({ tool, args });
  if (tool === routing.WORKSPACE_RESOLVE_TOOL) {
    return { content: [{ type: 'text', text: JSON.stringify({
      status: 'ok',
      resolution: 'resolved',
      product_id: 'prd-canonical',
      state: 'local_workspace_bound',
      canonical_write: 'none',
      product_selection_changed: false,
    }) }] };
  }
  if (tool === routing.PRODUCT_SELECT_TOOL) {
    return { content: [{ type: 'text', text: JSON.stringify({
      status: 'ok', selected_product_id: args.product_id,
    }) }] };
  }
  throw new Error('unexpected tool ' + tool);
};
const boundary = {
  host_kind: 'claude_code',
  host_session_id: 'session-1',
  host_turn_id: 'turn-1',
  plan_digest: 'sha256:plan',
  product_id: 'host-forged-product',
};
const hint = {
  ok: true,
  hostSessionId: 'session-1',
  candidatePath: '/operator/private/workspace',
  source: 'session.start.cwd',
};
const result = await routing.establishProductContext(callTool, hint, boundary);
if (!result.ok) throw new Error(JSON.stringify(result));
if (result.productId !== 'prd-canonical') throw new Error(JSON.stringify(result));
if (result.boundary.product_id !== 'prd-canonical') throw new Error(JSON.stringify(result));
if (calls.length !== 2) throw new Error(JSON.stringify(calls));
if (calls[0].tool !== 'bicameral.workspace.resolve') throw new Error(JSON.stringify(calls));
if (JSON.stringify(calls[0].args) !== JSON.stringify({ candidate_path: '/operator/private/workspace' })) {
  throw new Error(JSON.stringify(calls[0]));
}
if (calls[1].tool !== 'bicameral.product.select') throw new Error(JSON.stringify(calls));
if (JSON.stringify(calls[1].args) !== JSON.stringify({ product_id: 'prd-canonical' })) {
  throw new Error(JSON.stringify(calls[1]));
}
const visible = JSON.stringify(result);
if (visible.includes('/operator/private/workspace')) throw new Error('routing path leaked into result');
if (visible.includes('host-forged-product')) throw new Error('host product authority leaked');
""",
    )


def test_route_requires_same_session_hint_and_never_calls_mcp_on_mismatch(tmp_path: Path):
    _run_routing(
        tmp_path,
        r"""
let calls = 0;
const result = await routing.establishProductContext(
  async () => { calls += 1; throw new Error('must not call'); },
  { ok: true, hostSessionId: 'other-session', candidatePath: '/workspace' },
  { host_kind: 'claude_code', host_session_id: 'session-1', host_turn_id: 'turn-1', plan_digest: 'sha256:x' },
);
if (result.ok) throw new Error(JSON.stringify(result));
if (result.result.state !== 'product_context_unresolved') throw new Error(JSON.stringify(result));
if (result.result.limitations[0].code !== 'routing_hint_session_mismatch') throw new Error(JSON.stringify(result));
if (calls !== 0) throw new Error('MCP called before session binding check');
""",
    )


@pytest.mark.parametrize(
    ("code", "state", "count", "expected_state"),
    [
        ("unbound", "local_workspace_unbound", 0, "product_unbound"),
        ("repair_required", "local_workspace_repair_required", 1, "product_repair_required"),
        ("ambiguous", "local_workspace_bound", 2, "product_ambiguous"),
        ("unsafe_path", "local_workspace_unbound", 0, "product_routing_unsafe_path"),
    ],
)
def test_typed_resolve_failures_remain_distinct_and_never_select(
    tmp_path: Path,
    code: str,
    state: str,
    count: int,
    expected_state: str,
):
    _run_routing(
        tmp_path,
        f"""
const calls = [];
const result = await routing.establishProductContext(
  async (tool, args) => {{
    calls.push({{ tool, args }});
    return {{ content: [{{ type: 'text', text: JSON.stringify({{
      status: 'error', error_code: {json.dumps(code)}, state: {json.dumps(state)}, match_count: {count},
      canonical_write: 'none', product_selection_changed: false,
    }}) }}] }};
  }},
  {{ ok: true, hostSessionId: 's', candidatePath: '/workspace' }},
  {{ host_kind: 'claude_code', host_session_id: 's', host_turn_id: 't', plan_digest: 'sha256:x' }},
);
if (result.ok) throw new Error(JSON.stringify(result));
if (result.result.state !== {json.dumps(expected_state)}) throw new Error(JSON.stringify(result));
if (calls.length !== 1 || calls[0].tool !== routing.WORKSPACE_RESOLVE_TOOL) throw new Error(JSON.stringify(calls));
""",
    )


def test_crossed_resolve_error_tuple_fails_closed(tmp_path: Path):
    _run_routing(
        tmp_path,
        r"""
const result = routing.normalizeWorkspaceResolveResult({ content: [{
  type: 'text',
  text: JSON.stringify({
    status: 'error',
    error_code: 'repair_required',
    state: 'local_workspace_bound',
    match_count: 1,
  }),
}] });
if (result.ok || result.state !== 'product_routing_invalid_response') throw new Error(JSON.stringify(result));
if (result.code !== 'workspace_resolve_invalid_error_tuple') throw new Error(JSON.stringify(result));
""",
    )


def test_resolve_success_cannot_claim_write_or_implicit_selection(tmp_path: Path):
    _run_routing(
        tmp_path,
        r"""
for (const bad of [
  { canonical_write: 'product', product_selection_changed: false },
  { canonical_write: 'none', product_selection_changed: true },
]) {
  const result = routing.normalizeWorkspaceResolveResult({ content: [{
    type: 'text',
    text: JSON.stringify({
      status: 'ok', resolution: 'resolved', product_id: 'prd-1', state: 'local_workspace_bound', ...bad,
    }),
  }] });
  if (result.ok || result.code !== 'workspace_resolve_invalid_success') throw new Error(JSON.stringify(result));
}
""",
    )


def test_conflicting_resolve_payloads_fail_closed(tmp_path: Path):
    _run_routing(
        tmp_path,
        r"""
const ok = (id) => ({
  status: 'ok', resolution: 'resolved', product_id: id, state: 'local_workspace_bound',
  canonical_write: 'none', product_selection_changed: false,
});
const result = routing.normalizeWorkspaceResolveResult({ content: [
  { type: 'text', text: JSON.stringify(ok('prd-1')) },
  { type: 'text', text: JSON.stringify(ok('prd-2')) },
] });
if (result.ok || result.code !== 'workspace_resolve_conflict') throw new Error(JSON.stringify(result));
""",
    )


def test_product_select_must_echo_exact_resolved_product(tmp_path: Path):
    _run_routing(
        tmp_path,
        r"""
const result = routing.normalizeProductSelectResult({ content: [{
  type: 'text', text: JSON.stringify({ status: 'ok', selected_product_id: 'prd-other' }),
}] }, 'prd-expected');
if (result.ok || result.state !== 'product_selection_failed') throw new Error(JSON.stringify(result));
if (result.code !== 'product_select_id_mismatch') throw new Error(JSON.stringify(result));
""",
    )


def test_superseded_boundary_stops_before_product_select(tmp_path: Path):
    _run_routing(
        tmp_path,
        r"""
let current = true;
const calls = [];
const callTool = async (tool, args) => {
  calls.push({ tool, args });
  if (tool === routing.WORKSPACE_RESOLVE_TOOL) {
    current = false;
    return { content: [{ type: 'text', text: JSON.stringify({
      status: 'ok', resolution: 'resolved', product_id: 'prd-1', state: 'local_workspace_bound',
      canonical_write: 'none', product_selection_changed: false,
    }) }] };
  }
  throw new Error('stale boundary reached selection');
};
const result = await routing.establishProductContext(
  callTool,
  { ok: true, hostSessionId: 's', candidatePath: '/workspace' },
  { host_kind: 'claude_code', host_session_id: 's', host_turn_id: 't', plan_digest: 'sha256:x' },
  () => current,
);
if (!result.superseded) throw new Error(JSON.stringify(result));
if (calls.length !== 1 || calls[0].tool !== routing.WORKSPACE_RESOLVE_TOOL) throw new Error(JSON.stringify(calls));
""",
    )


def test_routing_response_is_bounded_before_parsing(tmp_path: Path):
    _run_routing(
        tmp_path,
        r"""
const result = routing.normalizeWorkspaceResolveResult({ content: [
  { type: 'text', text: 'x'.repeat(32769) },
] });
if (result.ok || result.state !== 'product_routing_invalid_response') throw new Error(JSON.stringify(result));
if (result.code !== 'product_routing_response_too_large') throw new Error(JSON.stringify(result));
""",
    )
