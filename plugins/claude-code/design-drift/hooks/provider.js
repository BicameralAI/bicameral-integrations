function objectOrNull(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : null
}

function stringOrNull(value) {
  return typeof value === 'string' && value.trim().length > 0 ? value : null
}

/**
 * Claude Code can deliver PostToolUse inside subagents. Design Drift v0.1 is
 * intentionally main-thread only because ManagedPlanningBoundaryV1 has no
 * agent identity dimension. A subagent ExitPlanMode must never replace the
 * main session's drift state.
 */
export function planningThreadDisposition(event) {
  const e = objectOrNull(event)
  if (!e || e.tool_name !== 'ExitPlanMode') {
    return { eligible: false, reason: 'not_planning_boundary' }
  }
  if (stringOrNull(e.agent_id)) {
    return { eligible: false, reason: 'subagent_boundary_ignored' }
  }
  return { eligible: true, reason: null }
}

/**
 * Capture the provider-authored session-start cwd once as a routing hint.
 * Claude's later cwd is mutable after cd/worktree changes, so it is never used
 * as Product identity and is not refreshed from PostToolUse events.
 *
 * This hint is deliberately not sent anywhere until the host-neutral
 * bicameral.workspace.resolve seam in BicameralAI/bicameral-mcp#871 exists.
 */
export function sessionRoutingHintFromStart(event) {
  const e = objectOrNull(event)
  if (!e) return { ok: false, reason: 'session_start_missing' }

  const hostSessionId = stringOrNull(e.session_id)
  const candidatePath = stringOrNull(e.cwd)
  if (!hostSessionId) return { ok: false, reason: 'session_id_missing' }
  if (!candidatePath) return { ok: false, reason: 'session_root_missing' }

  return {
    ok: true,
    hostSessionId,
    candidatePath,
    source: 'session.start.cwd',
  }
}
