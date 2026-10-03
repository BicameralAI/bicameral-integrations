import {
  MCP_SERVER,
  MCP_TOOL,
  buildPreflightArguments,
  detailText,
  planningBoundaryFromClassicPostToolUse,
  statusText,
} from './drift.js'
import { normalizeBoundedMcpResult } from './integrity.js'
import { planningThreadDisposition, sessionRoutingHintFromStart } from './provider.js'

let latestBoundary = null
let latestResult = null
let lastBoundaryKey = null
let activeBoundaryKey = null
let inFlightKey = null
let scheduledKey = null
let sessionRoutingHint = null

function resetSessionState() {
  latestBoundary = null
  latestResult = null
  lastBoundaryKey = null
  activeBoundaryKey = null
  inFlightKey = null
  scheduledKey = null
  sessionRoutingHint = null
}

function ignorePromiseFailure(value) {
  if (value && typeof value.catch === 'function') value.catch(() => {})
}

function safeStatus($, text) {
  try {
    ignorePromiseFailure($.ui.status(text))
  } catch {
    // Presentation failure must never affect Claude execution.
  }
}

function safeToast($, text) {
  try {
    ignorePromiseFailure($.ui.toast(text))
  } catch {
    // Presentation failure must never affect Claude execution.
  }
}

function setResult($, result) {
  latestResult = result
  safeStatus($, result?.state === 'runtime_degraded' ? 'Design Drift: plugin runtime degraded' : statusText(result))
  if (result?.state === 'contradiction') {
    safeToast($, 'Bicameral found a design contradiction. Run /bicameral-drift to review it.')
  }
}

function runtimeDegraded($, boundary = null, code = 'plugin_runtime_error') {
  setResult($, {
    state: 'runtime_degraded',
    outcome: null,
    analysisStatus: null,
    classes: [],
    limitations: [{ code }],
    boundary,
  })
}

async function runPreflight($, boundary, boundaryKey) {
  if (!boundaryKey || activeBoundaryKey !== boundaryKey) return latestResult
  if (inFlightKey === boundaryKey || scheduledKey === boundaryKey) return latestResult

  inFlightKey = boundaryKey
  setResult($, { state: 'analyzing', boundary })
  try {
    const response = await $.mcp.call(MCP_SERVER, MCP_TOOL, buildPreflightArguments(boundary))
    if (activeBoundaryKey === boundaryKey) {
      setResult($, normalizeBoundedMcpResult(response, boundary))
    }
  } catch {
    if (activeBoundaryKey === boundaryKey) {
      setResult($, {
        state: 'mcp_unavailable',
        outcome: null,
        analysisStatus: null,
        classes: [],
        limitations: [{ code: 'mcp_call_failed' }],
        boundary,
      })
    }
  } finally {
    if (inFlightKey === boundaryKey) inFlightKey = null
  }
  return latestResult
}

export function register(on) {
  on('session.start', async ($, e, next) => {
    resetSessionState()
    const routing = sessionRoutingHintFromStart(e)
    sessionRoutingHint = routing.ok ? routing : null
    try {
      await $.command.register({
        name: 'bicameral-drift',
        description: 'Show the latest Bicameral design-plan drift result',
        argumentHint: '[refresh]',
      })
    } catch {
      // A command-name conflict must not prevent the rest of the Mod from loading.
    }
    return next(e)
  })

  on('classic.PostToolUse', async ($, e, next) => {
    const thread = planningThreadDisposition(e)
    if (!thread.eligible) {
      // In particular, subagent ExitPlanMode must not clear or replace the
      // main-thread result because v0.1 has no governed agent identity field.
      return next(e)
    }

    let parsed
    try {
      parsed = await planningBoundaryFromClassicPostToolUse(e)
    } catch {
      latestBoundary = null
      lastBoundaryKey = null
      activeBoundaryKey = null
      runtimeDegraded($, null, 'planning_boundary_processing_failed')
      return next(e)
    }

    if (!parsed.ok) {
      latestBoundary = null
      lastBoundaryKey = null
      activeBoundaryKey = null
      setResult($, {
        state: parsed.reason,
        outcome: null,
        analysisStatus: null,
        classes: [],
        limitations: [{ code: parsed.reason }],
        boundary: null,
      })
      return next(e)
    }

    latestBoundary = parsed.boundary
    activeBoundaryKey = parsed.key
    if (parsed.key === lastBoundaryKey || parsed.key === inFlightKey || parsed.key === scheduledKey) {
      return next(e)
    }

    lastBoundaryKey = parsed.key
    scheduledKey = parsed.key
    setResult($, { state: 'analyzing', boundary: parsed.boundary })
    try {
      const scheduled = $.clock.after(0, async () => {
        if (scheduledKey === parsed.key) scheduledKey = null
        await runPreflight($, parsed.boundary, parsed.key)
      })
      ignorePromiseFailure(scheduled)
    } catch {
      if (scheduledKey === parsed.key) scheduledKey = null
      runtimeDegraded($, parsed.boundary, 'background_schedule_failed')
    }
    return next(e)
  })

  on('command.run', { command: 'bicameral-drift' }, async ($, e) => {
    const wantsRefresh = (e.args || '').trim().toLowerCase() === 'refresh'
    try {
      if ((wantsRefresh || !latestResult) && latestBoundary) {
        if (inFlightKey !== activeBoundaryKey && scheduledKey !== activeBoundaryKey) {
          await runPreflight($, latestBoundary, activeBoundaryKey)
        }
      }
      if (latestResult?.state === 'runtime_degraded') {
        return {
          text: [
            'Bicameral Design Drift',
            'Design Drift: plugin runtime degraded',
            'Advisory only. No drift conclusion is available from this event.',
          ].join('\n'),
        }
      }
      return { text: detailText(latestResult) }
    } catch {
      runtimeDegraded($, latestBoundary, 'command_render_failed')
      return {
        text: [
          'Bicameral Design Drift',
          'Design Drift: plugin runtime degraded',
          'Advisory only. No drift conclusion is available from this event.',
        ].join('\n'),
      }
    }
  })

  on('session.end', async ($, e, next) => {
    resetSessionState()
    return next(e)
  })
}

// sessionRoutingHint is intentionally captured but not consumed yet. Product
// routing remains blocked on the accepted host-neutral MCP seam in #871.
void sessionRoutingHint
