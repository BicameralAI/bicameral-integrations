import { extractMcpPayloads } from './drift.js'

export const WORKSPACE_RESOLVE_TOOL = 'bicameral.workspace.resolve'
export const PRODUCT_SELECT_TOOL = 'bicameral.product.select'

const MAX_ROUTING_CONTENT_ITEMS = 8
const MAX_ROUTING_JSON_CHARS = 32_768

const RESOLVE_ERROR_STATES = new Map([
  ['unbound', 'product_unbound'],
  ['repair_required', 'product_repair_required'],
  ['ambiguous', 'product_ambiguous'],
  ['unsafe_path', 'product_routing_unsafe_path'],
  ['candidate_path_invalid', 'product_routing_invalid_hint'],
  ['workspace_resolve_invalid_response', 'product_routing_invalid_response'],
  ['daemon_protocol_mismatch', 'protocol_mismatch'],
  ['daemon_capability_error', 'capability_unavailable'],
  ['daemon_unavailable', 'mcp_unavailable'],
  ['daemon_error', 'mcp_unavailable'],
])

const SELECT_ERROR_STATES = new Map([
  ['product_id_invalid', 'product_selection_failed'],
  ['daemon_protocol_mismatch', 'protocol_mismatch'],
  ['daemon_capability_error', 'capability_unavailable'],
  ['daemon_unavailable', 'mcp_unavailable'],
  ['daemon_error', 'mcp_unavailable'],
])

function objectOrNull(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : null
}

function contractString(value) {
  return typeof value === 'string' && value.trim().length > 0 ? value : null
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

function measureMcpResult(result) {
  const content = Array.isArray(result?.content) ? result.content : []
  if (content.length > MAX_ROUTING_CONTENT_ITEMS) return 'product_routing_response_too_many_content_items'

  let total = 0
  for (const item of content) {
    if (item?.type === 'text' && typeof item.text === 'string') {
      total += item.text.length
      if (total > MAX_ROUTING_JSON_CHARS) return 'product_routing_response_too_large'
    }
  }

  const structured = objectOrNull(result?.structuredContent)
  if (structured) {
    try {
      total += JSON.stringify(structured).length
    } catch {
      return 'product_routing_structured_content_unserializable'
    }
  }
  return total > MAX_ROUTING_JSON_CHARS ? 'product_routing_response_too_large' : null
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`
  const obj = objectOrNull(value)
  if (!obj) return JSON.stringify(value)
  return `{${Object.keys(obj)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${canonicalJson(obj[key])}`)
    .join(',')}}`
}

function uniqueProjections(payloads, project) {
  const byCanonical = new Map()
  for (const payload of payloads) {
    const projected = project(payload)
    if (!projected) continue
    byCanonical.set(canonicalJson(projected), projected)
  }
  return Array.from(byCanonical.values())
}

function resolveProjection(payload) {
  const root = objectOrNull(payload)
  if (!root) return null

  if (root.status === 'ok') {
    return {
      kind: 'ok',
      resolution: root.resolution,
      productId: root.product_id,
      state: root.state,
      canonicalWrite: root.canonical_write,
      productSelectionChanged: root.product_selection_changed,
    }
  }

  if (root.status === 'error' && contractString(root.error_code)) {
    return {
      kind: 'error',
      code: root.error_code,
      state: root.state,
      matchCount: root.match_count,
    }
  }
  return null
}

function validResolveFailureTuple(projected) {
  const count = projected.matchCount
  if (projected.code === 'unbound') {
    return projected.state === 'local_workspace_unbound' && (count === 0 || count === 1)
  }
  if (projected.code === 'repair_required') {
    return projected.state === 'local_workspace_repair_required' && count === 1
  }
  if (projected.code === 'ambiguous') {
    return projected.state === 'local_workspace_bound' && Number.isInteger(count) && count >= 2
  }
  if (projected.code === 'unsafe_path') {
    return projected.state === 'local_workspace_unbound' && count === 0
  }
  return true
}

export function normalizeWorkspaceResolveResult(mcpResult) {
  const sizeFailure = measureMcpResult(mcpResult)
  if (sizeFailure) return { ok: false, state: 'product_routing_invalid_response', code: sizeFailure }

  const payloads = extractMcpPayloads(mcpResult)
  const projected = uniqueProjections(payloads, resolveProjection)
  if (projected.length !== 1) {
    return {
      ok: false,
      state: 'product_routing_invalid_response',
      code: projected.length > 1 ? 'workspace_resolve_conflict' : 'workspace_resolve_missing',
    }
  }

  const value = projected[0]
  if (value.kind === 'ok') {
    if (mcpResult?.isError === true) {
      return { ok: false, state: 'product_routing_invalid_response', code: 'workspace_resolve_success_error_conflict' }
    }
    const productId = contractString(value.productId)
    if (
      !productId ||
      value.resolution !== 'resolved' ||
      value.state !== 'local_workspace_bound' ||
      value.canonicalWrite !== 'none' ||
      value.productSelectionChanged !== false
    ) {
      return { ok: false, state: 'product_routing_invalid_response', code: 'workspace_resolve_invalid_success' }
    }
    return { ok: true, productId }
  }

  const state = RESOLVE_ERROR_STATES.get(value.code)
  if (!state) {
    return { ok: false, state: 'product_routing_error', code: 'workspace_resolve_unrecognized_error' }
  }
  if (!validResolveFailureTuple(value)) {
    return { ok: false, state: 'product_routing_invalid_response', code: 'workspace_resolve_invalid_error_tuple' }
  }
  return { ok: false, state, code: value.code }
}

function selectProjection(payload) {
  const root = objectOrNull(payload)
  if (!root) return null
  if (root.status === 'ok' && contractString(root.selected_product_id)) {
    return { kind: 'ok', productId: root.selected_product_id }
  }
  if (root.status === 'error' && contractString(root.error_code)) {
    return { kind: 'error', code: root.error_code }
  }
  if (root.status === 'rejected') return { kind: 'rejected' }
  return null
}

export function normalizeProductSelectResult(mcpResult, expectedProductId) {
  const expected = contractString(expectedProductId)
  if (!expected) return { ok: false, state: 'product_selection_failed', code: 'product_selection_expected_id_invalid' }

  const sizeFailure = measureMcpResult(mcpResult)
  if (sizeFailure) return { ok: false, state: 'product_selection_failed', code: sizeFailure }

  const payloads = extractMcpPayloads(mcpResult)
  const projected = uniqueProjections(payloads, selectProjection)
  if (projected.length !== 1) {
    return {
      ok: false,
      state: 'product_selection_failed',
      code: projected.length > 1 ? 'product_select_conflict' : 'product_select_missing',
    }
  }

  const value = projected[0]
  if (value.kind === 'ok') {
    if (mcpResult?.isError === true) {
      return { ok: false, state: 'product_selection_failed', code: 'product_select_success_error_conflict' }
    }
    if (value.productId !== expected) {
      return { ok: false, state: 'product_selection_failed', code: 'product_select_id_mismatch' }
    }
    return { ok: true, productId: value.productId }
  }

  if (value.kind === 'rejected') {
    return { ok: false, state: 'product_selection_failed', code: 'product_select_rejected' }
  }

  const state = SELECT_ERROR_STATES.get(value.code)
  return state
    ? { ok: false, state, code: value.code }
    : { ok: false, state: 'product_selection_failed', code: 'product_select_unrecognized_error' }
}

/**
 * Establish Product context through the accepted MCP routing seam.
 *
 * The provider routing hint is never Product identity. The canonical Product id
 * comes only from bicameral.workspace.resolve and becomes usable only after the
 * same MCP process accepts bicameral.product.select. The caller supplies a
 * two-argument tool caller already bound to the connected Bicameral MCP server.
 */
export async function establishProductContext(callTool, routingHint, boundary, isCurrent = () => true) {
  const requested = objectOrNull(boundary)
  const cleanBoundary = requested ? { ...requested } : null
  if (cleanBoundary) delete cleanBoundary.product_id

  if (!cleanBoundary || !contractString(cleanBoundary.host_session_id)) {
    return {
      ok: false,
      result: failureResult('product_context_unresolved', cleanBoundary, 'planning_boundary_session_missing'),
    }
  }

  const hint = objectOrNull(routingHint)
  const candidatePath = hint?.ok === true ? contractString(hint.candidatePath) : null
  const hintSessionId = hint?.ok === true ? contractString(hint.hostSessionId) : null
  if (!candidatePath || !hintSessionId) {
    return {
      ok: false,
      result: failureResult('product_context_unresolved', cleanBoundary, 'session_routing_hint_unavailable'),
    }
  }
  if (hintSessionId !== cleanBoundary.host_session_id) {
    return {
      ok: false,
      result: failureResult('product_context_unresolved', cleanBoundary, 'routing_hint_session_mismatch'),
    }
  }
  if (!isCurrent()) return { ok: false, superseded: true }

  let resolveResponse
  try {
    resolveResponse = await callTool(WORKSPACE_RESOLVE_TOOL, { candidate_path: candidatePath })
  } catch {
    return {
      ok: false,
      result: failureResult('mcp_unavailable', cleanBoundary, 'workspace_resolve_call_failed'),
    }
  }

  if (!isCurrent()) return { ok: false, superseded: true }
  const resolved = normalizeWorkspaceResolveResult(resolveResponse)
  if (!resolved.ok) {
    return { ok: false, result: failureResult(resolved.state, cleanBoundary, resolved.code) }
  }

  let selectResponse
  try {
    selectResponse = await callTool(PRODUCT_SELECT_TOOL, { product_id: resolved.productId })
  } catch {
    return {
      ok: false,
      result: failureResult('mcp_unavailable', cleanBoundary, 'product_select_call_failed'),
    }
  }

  if (!isCurrent()) return { ok: false, superseded: true }
  const selected = normalizeProductSelectResult(selectResponse, resolved.productId)
  if (!selected.ok) {
    return { ok: false, result: failureResult(selected.state, cleanBoundary, selected.code) }
  }

  return {
    ok: true,
    productId: selected.productId,
    boundary: { ...cleanBoundary, product_id: selected.productId },
  }
}
