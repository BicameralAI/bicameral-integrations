import {
  MCP_SERVER,
  MCP_TOOL,
  buildPreflightArguments,
  detailText,
  normalizeMcpResult,
  planningBoundaryFromClassicPostToolUse,
  statusText,
} from './drift.js'

let latestBoundary = null
let latestResult = null
let lastBoundaryKey = null
let activeBoundaryKey = null
let inFlightKey = null

function resetSessionState() {
  latestBoundary = null
  latestResult = null
  lastBoundaryKey = null
  activeBoundaryKey = null
  inFlightKey = null
}

function setResult($, result) {
  latestResult = result
  $.ui.status(statusText(result))
  if (result?.state === 'contradiction') {
    $.ui.toast('Bicameral found a design contradiction. Run /bicameral-drift to review it.')
  }
}

async function runPreflight($, boundary, boundaryKey) {
  if (!boundaryKey || activeBoundaryKey !== boundaryKey) return latestResult
  inFlightKey = boundaryKey
  setResult($, { state: 'analyzing', boundary })
  try {
    const response = await $.mcp.call(MCP_SERVER, MCP_TOOL, buildPreflightArguments(boundary))
    if (activeBoundaryKey === boundaryKey) {
      setResult($, normalizeMcpResult(response, boundary))
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
    const parsed = await planningBoundaryFromClassicPostToolUse(e)
    if (!parsed.ok) {
      if (e?.tool_name === 'ExitPlanMode' && parsed.reason !== 'not_planning_boundary') {
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
      }
      return next(e)
    }

    latestBoundary = parsed.boundary
    activeBoundaryKey = parsed.key
    if (parsed.key === lastBoundaryKey || parsed.key === inFlightKey) return next(e)

    lastBoundaryKey = parsed.key
    inFlightKey = parsed.key
    setResult($, { state: 'analyzing', boundary: parsed.boundary })
    $.clock.after(0, async () => {
      await runPreflight($, parsed.boundary, parsed.key)
    })
    return next(e)
  })

  on('command.run', { command: 'bicameral-drift' }, async ($, e) => {
    const wantsRefresh = (e.args || '').trim().toLowerCase() === 'refresh'
    if ((wantsRefresh || !latestResult) && latestBoundary) {
      await runPreflight($, latestBoundary, activeBoundaryKey)
    }
    return { text: detailText(latestResult) }
  })

  on('session.end', async ($, e, next) => {
    resetSessionState()
    return next(e)
  })
}
