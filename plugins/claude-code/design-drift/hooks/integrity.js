import { extractMcpPayloads, normalizeMcpResult } from './drift.js'

const MAX_CONTENT_ITEMS = 16
const MAX_TOTAL_JSON_CHARS = 262_144
const MAX_CANDIDATES = 256
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const SHA256_RE = /^sha256:[0-9a-f]{64}$/
const SAFE_IDENTITY_RE = /^[\x20-\x7e]{1,256}$/

const MANAGED_OUTCOMES = new Set(['binding_validated', 'no_candidate'])
const ANALYSIS_STATUSES = new Set([
  'not_attempted',
  'provider_unavailable',
  'invalid_trace',
  'timed_out',
  'completed',
])
const SEMANTIC_CLASSES = new Set([
  'proposed',
  'contradiction',
  'evidence',
  'searched_scope',
  'unknown',
  'timeout',
  'no_candidate',
])
const LIMITATION_CODES = new Set([
  'missing_governing_spec',
  'workspace_unavailable',
  'invalid_boundary',
  'invalid_git_head',
  'invalid_artifact_path',
  'invalid_blob_id',
  'invalid_content_digest',
  'repository_mismatch',
  'revision_unavailable',
  'artifact_unavailable',
  'blob_mismatch',
  'content_digest_mismatch',
  'claim_trace_provider_unavailable',
  'claim_trace_invalid',
  'claim_trace_incomplete',
  'analysis_timed_out',
  'kernel_unavailable',
  'product_context_required',
  'daemon_protocol_mismatch',
  'daemon_capability_error',
  'daemon_unavailable',
  'mcp_tool_error',
  'mcp_call_failed',
  'managed_preflight_missing',
  'mcp_result_unparseable',
  'managed_boundary_missing',
  'managed_boundary_host_kind_mismatch',
  'managed_boundary_host_session_id_mismatch',
  'managed_boundary_host_turn_id_mismatch',
  'managed_boundary_plan_digest_mismatch',
  'managed_boundary_product_id_missing',
  'managed_boundary_product_id_mismatch',
  'unsupported_candidate_contract_version',
  'candidate_set_binding_missing',
  'candidate_set_identity_invalid',
  'candidate_set_product_id_mismatch',
  'candidate_set_host_session_id_mismatch',
  'candidate_set_plan_digest_mismatch',
  'candidate_set_spec_binding_mismatch',
  'candidate_set_candidates_invalid',
  'candidate_id_missing',
  'duplicate_candidate_id',
])

function objectOrNull(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : null
}

function failureResult(state, boundary, code) {
  return {
    state,
    outcome: null,
    analysisStatus: null,
    classes: [],
    limitations: [{ code }],
    boundary,
  }
}

function sortedClone(value) {
  if (Array.isArray(value)) return value.map(sortedClone)
  const obj = objectOrNull(value)
  if (!obj) return value
  const out = {}
  for (const key of Object.keys(obj).sort()) out[key] = sortedClone(obj[key])
  return out
}

function canonicalJson(value) {
  return JSON.stringify(sortedClone(value))
}

function uniqueRelevant(payloads, extractor) {
  const byCanonical = new Map()
  for (const payload of payloads) {
    const value = extractor(payload)
    if (!value) continue
    byCanonical.set(canonicalJson(value), value)
  }
  return Array.from(byCanonical.values())
}

function managedFromPayload(payload) {
  const root = objectOrNull(payload)
  if (!root) return null
  const direct = objectOrNull(root.managed_preflight)
  if (direct) return direct
  const result = objectOrNull(root.result)
  return result ? objectOrNull(result.managed_preflight) : null
}

function candidateSurfaceFromPayload(payload) {
  const root = objectOrNull(payload)
  return root ? objectOrNull(root.managed_mcp_candidate_set) : null
}

function typedErrorFromPayload(payload) {
  const root = objectOrNull(payload)
  return root && root.status === 'error' ? root : null
}

function measureRawResult(result) {
  const content = Array.isArray(result?.content) ? result.content : []
  if (content.length > MAX_CONTENT_ITEMS) return 'mcp_response_too_many_content_items'

  let total = 0
  for (const item of content) {
    if (item?.type === 'text' && typeof item.text === 'string') {
      total += item.text.length
      if (total > MAX_TOTAL_JSON_CHARS) return 'mcp_response_too_large'
    }
  }

  const structured = objectOrNull(result?.structuredContent)
  if (structured) {
    try {
      total += canonicalJson(structured).length
    } catch {
      return 'mcp_structured_content_unserializable'
    }
  }
  if (total > MAX_TOTAL_JSON_CHARS) return 'mcp_response_too_large'
  return null
}

function validIdentityString(value) {
  return typeof value === 'string' && SAFE_IDENTITY_RE.test(value)
}

function validateManaged(managed) {
  if (!managed || !MANAGED_OUTCOMES.has(managed.outcome)) return 'managed_outcome_invalid'

  const boundary = objectOrNull(managed.boundary)
  if (!boundary) return 'managed_boundary_missing'
  if (boundary.host_kind !== 'claude_code') return 'managed_host_kind_invalid'
  for (const field of ['host_session_id', 'host_turn_id', 'product_id']) {
    if (!validIdentityString(boundary[field])) return `managed_${field}_invalid`
  }
  if (!SHA256_RE.test(boundary.plan_digest || '')) return 'managed_plan_digest_invalid'

  const specDigest = managed.governing_spec_binding_digest
  if (specDigest != null && !SHA256_RE.test(specDigest)) return 'managed_spec_binding_digest_invalid'

  if (managed.analysis != null) {
    const analysis = objectOrNull(managed.analysis)
    if (!analysis || !ANALYSIS_STATUSES.has(analysis.status)) return 'managed_analysis_status_invalid'
    if (!Array.isArray(analysis.classes)) return 'managed_analysis_classes_invalid'
    for (const value of analysis.classes) {
      if (!SEMANTIC_CLASSES.has(value)) return 'managed_analysis_class_invalid'
    }
  }
  return null
}

function validateCandidateSurface(surface) {
  if (!surface) return null
  if (surface.contract_version !== 1) return 'unsupported_candidate_contract_version'
  const raw = objectOrNull(surface.daemon_candidate_set)
  const binding = raw ? objectOrNull(raw.binding) : null
  if (!raw || !binding) return 'candidate_set_binding_missing'
  if (!UUID_RE.test(raw.candidate_set_id || '')) return 'candidate_set_id_invalid'
  if (!SHA256_RE.test(raw.candidate_set_digest || '')) return 'candidate_set_digest_invalid'
  if (!validIdentityString(raw.session_lease_id)) return 'candidate_set_session_lease_id_invalid'
  if (!validIdentityString(binding.product_id)) return 'candidate_set_product_id_invalid'
  if (!validIdentityString(binding.host_session_id)) return 'candidate_set_host_session_id_invalid'
  if (!SHA256_RE.test(binding.plan_digest || '')) return 'candidate_set_plan_digest_invalid'
  if (!SHA256_RE.test(binding.governing_spec_binding_digest || '')) {
    return 'candidate_set_spec_binding_digest_invalid'
  }
  if (!Array.isArray(raw.candidates)) return 'candidate_set_candidates_invalid'
  if (raw.candidates.length > MAX_CANDIDATES) return 'candidate_set_too_large'

  const seen = new Set()
  for (const candidate of raw.candidates) {
    const id = objectOrNull(candidate)?.candidate_id
    if (!UUID_RE.test(id || '')) return 'candidate_id_invalid'
    if (seen.has(id)) return 'duplicate_candidate_id'
    seen.add(id)
  }
  return null
}

function sanitizedLimitations(limitations) {
  if (!Array.isArray(limitations)) return []
  const out = []
  for (const item of limitations.slice(0, 16)) {
    const code = objectOrNull(item)?.code
    out.push({ code: LIMITATION_CODES.has(code) ? code : 'unrecognized_limitation_code' })
  }
  return out
}

function sanitizeNormalized(result) {
  return {
    ...result,
    outcome: MANAGED_OUTCOMES.has(result.outcome) ? result.outcome : result.outcome == null ? null : 'unknown',
    analysisStatus: ANALYSIS_STATUSES.has(result.analysisStatus)
      ? result.analysisStatus
      : result.analysisStatus == null
        ? null
        : 'unknown',
    classes: Array.isArray(result.classes)
      ? result.classes.filter((value) => SEMANTIC_CLASSES.has(value))
      : [],
    limitations: sanitizedLimitations(result.limitations),
  }
}

/**
 * Validate and bound an MCP response before any value becomes persistent Mod
 * state or transcript-visible command text. This is a presentation-integrity
 * layer only; it does not make Claude's Mod chain a trusted governance witness.
 */
export function normalizeBoundedMcpResult(mcpResult, boundary) {
  const sizeFailure = measureRawResult(mcpResult)
  if (sizeFailure) return failureResult('response_integrity_error', boundary, sizeFailure)

  const payloads = extractMcpPayloads(mcpResult)
  const managed = uniqueRelevant(payloads, managedFromPayload)
  const candidateSurfaces = uniqueRelevant(payloads, candidateSurfaceFromPayload)
  const errors = uniqueRelevant(payloads, typedErrorFromPayload)

  if (managed.length > 1) {
    return failureResult('response_integrity_error', boundary, 'managed_preflight_conflict')
  }
  if (candidateSurfaces.length > 1) {
    return failureResult('response_integrity_error', boundary, 'candidate_surface_conflict')
  }
  if (errors.length > 1) {
    return failureResult('response_integrity_error', boundary, 'mcp_error_conflict')
  }
  if (errors.length && (managed.length || candidateSurfaces.length)) {
    return failureResult('response_integrity_error', boundary, 'mcp_success_error_conflict')
  }

  if (managed.length) {
    const managedFailure = validateManaged(managed[0])
    if (managedFailure) return failureResult('semantic_contract_invalid', boundary, managedFailure)
  }
  if (candidateSurfaces.length) {
    const candidateFailure = validateCandidateSurface(candidateSurfaces[0])
    if (candidateFailure) return failureResult('candidate_set_invalid', boundary, candidateFailure)
  }

  return sanitizeNormalized(normalizeMcpResult(mcpResult, boundary))
}
