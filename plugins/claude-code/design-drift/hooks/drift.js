export const MCP_SERVER = 'bicameral'
export const MCP_TOOL = 'bicameral.preflight'

const SHA256_PREFIX = 'sha256:'

function objectOrNull(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : null
}

function stringOrNull(value) {
  return typeof value === 'string' && value.length > 0 ? value : null
}

function listOfObjects(value) {
  return Array.isArray(value) ? value.filter((item) => objectOrNull(item)) : []
}

function listOfStrings(value) {
  return Array.isArray(value) ? value.filter((item) => typeof item === 'string') : []
}

export async function sha256Text(text) {
  const bytes = new TextEncoder().encode(text)
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  const hex = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
  return SHA256_PREFIX + hex
}

export async function planningBoundaryFromClassicPostToolUse(event) {
  const e = objectOrNull(event)
  if (!e || e.tool_name !== 'ExitPlanMode') {
    return { ok: false, reason: 'not_planning_boundary' }
  }

  const toolResponse = objectOrNull(e.tool_response)
  const plan = toolResponse ? stringOrNull(toolResponse.plan) : null
  if (!plan) {
    return { ok: false, reason: 'missing_plan_bytes' }
  }

  const hostSessionId = stringOrNull(e.session_id)
  const hostTurnId = stringOrNull(e.turn_id)
  if (!hostSessionId || !hostTurnId) {
    return { ok: false, reason: 'missing_boundary_identity' }
  }

  const planDigest = await sha256Text(plan)
  const managedPlanning = {
    host_kind: 'claude_code',
    host_session_id: hostSessionId,
    host_turn_id: hostTurnId,
    plan_digest: planDigest,
  }

  const productId = stringOrNull(e.product_id)
  if (productId) managedPlanning.product_id = productId

  return {
    ok: true,
    boundary: managedPlanning,
    key: ['claude_code', hostSessionId, hostTurnId, planDigest].join(':'),
  }
}

export function buildPreflightArguments(boundary) {
  return { managed_planning: { ...boundary } }
}

function parseTextContent(result) {
  const content = Array.isArray(result?.content) ? result.content : []
  for (const item of content) {
    if (item?.type !== 'text' || typeof item.text !== 'string') continue
    try {
      const parsed = JSON.parse(item.text)
      if (objectOrNull(parsed)) return parsed
    } catch {
      // A non-JSON text block is not a Bicameral structured result. Keep looking.
    }
  }
  return null
}

export function extractMcpPayload(result) {
  const structured = objectOrNull(result?.structuredContent)
  if (structured) return structured
  return parseTextContent(result)
}

function findManagedPreflight(payload) {
  const root = objectOrNull(payload)
  if (!root) return null
  const direct = objectOrNull(root.managed_preflight)
  if (direct) return direct
  const result = objectOrNull(root.result)
  if (!result) return null
  return objectOrNull(result.managed_preflight)
}

function normalizedLimitations(...values) {
  const out = []
  for (const value of values) {
    for (const item of listOfObjects(value)) {
      const code = stringOrNull(item.code)
      const detail = stringOrNull(item.detail)
      if (code || detail) out.push({ ...(code ? { code } : {}), ...(detail ? { detail } : {}) })
    }
  }
  return out
}

function candidateCount(managed) {
  const candidateSet = objectOrNull(managed?.candidate_set)
  return candidateSet && Array.isArray(candidateSet.candidates) ? candidateSet.candidates.length : null
}

export function normalizeMcpResult(mcpResult, boundary) {
  const payload = extractMcpPayload(mcpResult)
  if (!payload) {
    return {
      state: 'invalid_response',
      outcome: null,
      analysisStatus: null,
      classes: [],
      limitations: [{ code: 'mcp_result_unparseable' }],
      boundary,
    }
  }

  const managed = findManagedPreflight(payload)
  if (!managed) {
    return {
      state: 'managed_preflight_missing',
      outcome: null,
      analysisStatus: null,
      classes: [],
      limitations: [{ code: 'managed_preflight_missing' }],
      boundary,
      requestId: stringOrNull(payload.request_id),
    }
  }

  const analysis = objectOrNull(managed.analysis) || {}
  const outcome = stringOrNull(managed.outcome)
  const analysisStatus = stringOrNull(analysis.status)
  const classes = listOfStrings(analysis.classes)
  const limitations = normalizedLimitations(managed.limitations, analysis.limitations)
  const normalizedClasses = new Set(classes.map((item) => item.toLowerCase()))

  let state = 'incomplete'
  if (analysisStatus === 'completed') {
    if (normalizedClasses.has('contradiction')) state = 'contradiction'
    else if (normalizedClasses.has('proposed')) state = 'proposed'
    else if (outcome === 'no_candidate' || normalizedClasses.has('no_candidate')) state = 'no_candidate'
    else state = 'no_actionable_difference'
  } else if (analysisStatus === 'provider_unavailable') {
    state = 'provider_unavailable'
  } else if (analysisStatus === 'timed_out') {
    state = 'timed_out'
  } else if (analysisStatus === 'invalid_trace') {
    state = 'invalid_trace'
  } else if (analysisStatus === 'not_attempted' && outcome === 'no_candidate') {
    state = 'no_candidate_unanalyzed'
  } else if (outcome === 'no_candidate') {
    state = 'no_candidate_unanalyzed'
  }

  return {
    state,
    outcome,
    analysisStatus,
    classes,
    limitations,
    boundary: objectOrNull(managed.boundary) || boundary,
    requestId: stringOrNull(payload.request_id),
    governingSpecBindingDigest: stringOrNull(managed.governing_spec_binding_digest),
    governingSpec: objectOrNull(managed.governing_spec),
    candidateCount: candidateCount(managed),
    raw: managed,
  }
}

export function statusText(result) {
  if (!result) return 'Design Drift: no completed planning boundary yet'
  switch (result.state) {
    case 'analyzing':
      return 'Design Drift: analyzing…'
    case 'contradiction':
      return 'Design Drift: contradiction detected'
    case 'proposed': {
      const count = result.candidateCount
      return count == null
        ? 'Design Drift: proposed differences'
        : `Design Drift: ${count} proposed difference${count === 1 ? '' : 's'}`
    }
    case 'no_actionable_difference':
      return 'Design Drift: no actionable difference in analyzed scope'
    case 'no_candidate':
      return 'Design Drift: no candidate in analyzed scope'
    case 'no_candidate_unanalyzed':
      return 'Design Drift: no candidate · analysis incomplete'
    case 'provider_unavailable':
      return 'Design Drift: analysis provider unavailable'
    case 'timed_out':
      return 'Design Drift: analysis timed out'
    case 'invalid_trace':
      return 'Design Drift: analysis failed validation'
    case 'missing_plan_bytes':
      return 'Design Drift: plan boundary missing exact plan bytes'
    case 'missing_boundary_identity':
      return 'Design Drift: plan boundary identity incomplete'
    case 'mcp_unavailable':
      return 'Design Drift: Bicameral MCP unavailable'
    case 'managed_preflight_missing':
    case 'invalid_response':
      return 'Design Drift: invalid Bicameral response'
    default:
      return 'Design Drift: incomplete'
  }
}

export function detailText(result) {
  if (!result) {
    return [
      'Bicameral Design Drift',
      'No completed Bicameral planning boundary is available in this session.',
      'Run planning to completion, then use /bicameral-drift again.',
    ].join('\n')
  }

  const lines = ['Bicameral Design Drift', statusText(result), 'Advisory only. Bicameral remains the authority.']
  if (result.outcome) lines.push(`Outcome: ${result.outcome}`)
  if (result.analysisStatus) lines.push(`Analysis: ${result.analysisStatus}`)
  if (Array.isArray(result.classes) && result.classes.length) lines.push(`Classes: ${result.classes.join(', ')}`)
  if (result.governingSpecBindingDigest) lines.push(`Spec binding: ${result.governingSpecBindingDigest}`)
  if (result.candidateCount != null) lines.push(`Candidates: ${result.candidateCount}`)
  if (Array.isArray(result.limitations) && result.limitations.length) {
    lines.push('Limitations:')
    for (const limitation of result.limitations.slice(0, 8)) {
      const code = limitation.code || 'limitation'
      const detail = limitation.detail ? `: ${limitation.detail}` : ''
      lines.push(`- ${code}${detail}`)
    }
  }
  return lines.join('\n')
}
