export const MCP_SERVER = 'bicameral'
export const MCP_TOOL = 'bicameral.preflight'

const SHA256_PREFIX = 'sha256:'
const CANDIDATE_DISPLAY_CONTRACT_VERSION = 1

function objectOrNull(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : null
}

function stringOrNull(value) {
  return typeof value === 'string' && value.length > 0 ? value : null
}

function positiveIntegerOrNull(value) {
  return Number.isInteger(value) && value > 0 ? value : null
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
  const hostTurnId = stringOrNull(e.turn_id) || stringOrNull(e.tool_use_id)
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

function parseTextPayloads(result) {
  const payloads = []
  const content = Array.isArray(result?.content) ? result.content : []
  for (const item of content) {
    if (item?.type !== 'text' || typeof item.text !== 'string') continue
    try {
      const parsed = JSON.parse(item.text)
      if (objectOrNull(parsed)) payloads.push(parsed)
    } catch {
      // Non-JSON text is not a structured Bicameral result.
    }
  }
  return payloads
}

export function extractMcpPayloads(result) {
  const payloads = []
  const structured = objectOrNull(result?.structuredContent)
  if (structured) payloads.push(structured)
  payloads.push(...parseTextPayloads(result))
  return payloads
}

function findManagedPreflight(payloads) {
  for (const payload of payloads) {
    const root = objectOrNull(payload)
    if (!root) continue
    const direct = objectOrNull(root.managed_preflight)
    if (direct) return { managed: direct, payload: root }
    const result = objectOrNull(root.result)
    const nested = result ? objectOrNull(result.managed_preflight) : null
    if (nested) return { managed: nested, payload: root }
  }
  return null
}

function findCandidateSurface(payloads) {
  for (const payload of payloads) {
    const root = objectOrNull(payload)
    const surface = root ? objectOrNull(root.managed_mcp_candidate_set) : null
    if (surface) return surface
  }
  return null
}

function findTypedError(payloads) {
  for (const payload of payloads) {
    const root = objectOrNull(payload)
    if (!root || root.status !== 'error') continue
    return {
      code: stringOrNull(root.error_code) || 'mcp_tool_error',
      message: stringOrNull(root.message),
    }
  }
  return null
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

function boundaryMismatch(requestedBoundary, returnedBoundary) {
  const requested = objectOrNull(requestedBoundary)
  const returned = objectOrNull(returnedBoundary)
  if (!requested || !returned) return 'managed_boundary_missing'

  for (const field of ['host_kind', 'host_session_id', 'host_turn_id', 'plan_digest']) {
    if (stringOrNull(requested[field]) !== stringOrNull(returned[field])) {
      return `managed_boundary_${field}_mismatch`
    }
  }

  const returnedProductId = stringOrNull(returned.product_id)
  if (!returnedProductId) return 'managed_boundary_product_id_missing'

  const requestedProductId = stringOrNull(requested.product_id)
  if (requestedProductId && requestedProductId !== returnedProductId) {
    return 'managed_boundary_product_id_mismatch'
  }

  return null
}

function candidateSurfaceProjection(surface, requestedBoundary, returnedBoundary, governingSpecBindingDigest) {
  if (!surface) return { ok: true, candidateSet: null }

  if (surface.contract_version !== CANDIDATE_DISPLAY_CONTRACT_VERSION) {
    return { ok: false, reason: 'unsupported_candidate_contract_version' }
  }

  const raw = objectOrNull(surface.daemon_candidate_set)
  const binding = raw ? objectOrNull(raw.binding) : null
  if (!raw || !binding) return { ok: false, reason: 'candidate_set_binding_missing' }

  const generation = positiveIntegerOrNull(raw.candidate_set_generation)
  const candidateSetId = stringOrNull(raw.candidate_set_id)
  const candidateSetDigest = stringOrNull(raw.candidate_set_digest)
  const sessionLeaseId = stringOrNull(raw.session_lease_id)
  if (!generation || !candidateSetId || !candidateSetDigest || !sessionLeaseId) {
    return { ok: false, reason: 'candidate_set_identity_invalid' }
  }

  const requested = objectOrNull(requestedBoundary) || {}
  const returned = objectOrNull(returnedBoundary) || {}
  const expectedProductId = stringOrNull(requested.product_id) || stringOrNull(returned.product_id)
  const expectedSessionId = stringOrNull(requested.host_session_id)
  const expectedPlanDigest = stringOrNull(requested.plan_digest)
  const expectedSpecDigest = stringOrNull(governingSpecBindingDigest)

  if (!expectedProductId || stringOrNull(binding.product_id) !== expectedProductId) {
    return { ok: false, reason: 'candidate_set_product_id_mismatch' }
  }
  if (!expectedSessionId || stringOrNull(binding.host_session_id) !== expectedSessionId) {
    return { ok: false, reason: 'candidate_set_host_session_id_mismatch' }
  }
  if (!expectedPlanDigest || stringOrNull(binding.plan_digest) !== expectedPlanDigest) {
    return { ok: false, reason: 'candidate_set_plan_digest_mismatch' }
  }
  if (!expectedSpecDigest || stringOrNull(binding.governing_spec_binding_digest) !== expectedSpecDigest) {
    return { ok: false, reason: 'candidate_set_spec_binding_mismatch' }
  }

  const candidates = Array.isArray(raw.candidates) ? raw.candidates : null
  if (!candidates) return { ok: false, reason: 'candidate_set_candidates_invalid' }

  const seen = new Set()
  for (const candidate of candidates) {
    const candidateId = stringOrNull(objectOrNull(candidate)?.candidate_id)
    if (!candidateId) return { ok: false, reason: 'candidate_id_missing' }
    if (seen.has(candidateId)) return { ok: false, reason: 'duplicate_candidate_id' }
    seen.add(candidateId)
  }

  return {
    ok: true,
    candidateSet: {
      contractVersion: surface.contract_version,
      candidateSetId,
      generation,
      candidateSetDigest,
      sessionLeaseId,
      productId: expectedProductId,
      hostSessionId: expectedSessionId,
      planDigest: expectedPlanDigest,
      governingSpecBindingDigest: expectedSpecDigest,
      candidateCount: candidates.length,
    },
  }
}

function mcpErrorState(code) {
  switch (code) {
    case 'product_context_required':
      return 'product_context_required'
    case 'daemon_protocol_mismatch':
      return 'protocol_mismatch'
    case 'daemon_capability_error':
      return 'capability_unavailable'
    case 'daemon_unavailable':
      return 'mcp_unavailable'
    default:
      return 'mcp_error'
  }
}

function failureResult(state, boundary, code, extra = {}) {
  return {
    state,
    outcome: null,
    analysisStatus: null,
    classes: [],
    limitations: [{ code }],
    boundary,
    ...extra,
  }
}

export function normalizeMcpResult(mcpResult, boundary) {
  const payloads = extractMcpPayloads(mcpResult)
  const typedError = findTypedError(payloads)
  if (mcpResult?.isError === true || typedError) {
    const code = typedError?.code || 'mcp_tool_error'
    return failureResult(mcpErrorState(code), boundary, code)
  }

  if (!payloads.length) {
    return failureResult('invalid_response', boundary, 'mcp_result_unparseable')
  }

  const found = findManagedPreflight(payloads)
  if (!found) {
    return failureResult('managed_preflight_missing', boundary, 'managed_preflight_missing')
  }

  const { managed, payload } = found
  const returnedBoundary = objectOrNull(managed.boundary)
  const mismatch = boundaryMismatch(boundary, returnedBoundary)
  if (mismatch) {
    return failureResult('boundary_mismatch', boundary, mismatch, {
      requestId: stringOrNull(payload.request_id),
    })
  }

  const governingSpecBindingDigest = stringOrNull(managed.governing_spec_binding_digest)
  const candidateSurface = findCandidateSurface(payloads)
  const projected = candidateSurfaceProjection(
    candidateSurface,
    boundary,
    returnedBoundary,
    governingSpecBindingDigest,
  )
  if (!projected.ok) {
    return failureResult('candidate_set_invalid', boundary, projected.reason, {
      requestId: stringOrNull(payload.request_id),
    })
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
    else state = 'completed_unclassified'
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

  const candidateCount = projected.candidateSet?.candidateCount ?? null

  return {
    state,
    outcome,
    analysisStatus,
    classes,
    limitations,
    boundary: returnedBoundary,
    requestId: stringOrNull(payload.request_id),
    governingSpecBindingDigest,
    candidateCount,
    candidateSet: projected.candidateSet,
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
    case 'completed_unclassified':
      return 'Design Drift: analysis completed · no drift conclusion asserted'
    case 'no_candidate':
      return 'Design Drift: no candidate in analyzed scope'
    case 'no_candidate_unanalyzed':
      return 'Design Drift: no candidate · analysis incomplete'
    case 'provider_unavailable':
      return 'Design Drift: semantic analysis provider unavailable'
    case 'timed_out':
      return 'Design Drift: analysis timed out'
    case 'invalid_trace':
      return 'Design Drift: analysis failed validation'
    case 'missing_plan_bytes':
      return 'Design Drift: plan boundary missing exact plan bytes'
    case 'missing_boundary_identity':
      return 'Design Drift: plan boundary identity incomplete'
    case 'product_context_required':
      return 'Design Drift: Bicameral Product context required'
    case 'protocol_mismatch':
      return 'Design Drift: Bicameral protocol mismatch'
    case 'capability_unavailable':
      return 'Design Drift: required Bicameral capability unavailable'
    case 'mcp_unavailable':
      return 'Design Drift: Bicameral MCP unavailable'
    case 'boundary_mismatch':
      return 'Design Drift: response boundary mismatch'
    case 'candidate_set_invalid':
      return 'Design Drift: CandidateSet response failed integrity checks'
    case 'mcp_error':
      return 'Design Drift: Bicameral MCP returned an error'
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
  if (result.candidateSet?.candidateSetId) lines.push(`Candidate set: ${result.candidateSet.candidateSetId}`)
  if (result.candidateSet?.generation) lines.push(`Candidate generation: ${result.candidateSet.generation}`)
  if (Array.isArray(result.limitations) && result.limitations.length) {
    lines.push('Limitation codes:')
    for (const limitation of result.limitations.slice(0, 8)) {
      lines.push(`- ${limitation.code || 'limitation'}`)
    }
  }
  return lines.join('\n')
}
