const ROUTING_STATUS = new Map([
  ['product_context_unresolved', 'Design Drift: Bicameral Product context unresolved'],
  ['product_unbound', 'Design Drift: workspace is not bound to a Bicameral Product'],
  ['product_repair_required', 'Design Drift: workspace binding requires repair'],
  ['product_ambiguous', 'Design Drift: workspace resolves to multiple Products'],
  ['product_routing_unsafe_path', 'Design Drift: workspace routing hint rejected'],
  ['product_routing_invalid_hint', 'Design Drift: workspace routing hint invalid'],
  ['product_routing_invalid_response', 'Design Drift: Product routing response failed integrity checks'],
  ['product_routing_error', 'Design Drift: Product routing failed'],
  ['product_selection_failed', 'Design Drift: Bicameral Product selection failed'],
])

export function routingStatusText(result) {
  return ROUTING_STATUS.get(result?.state) || null
}

export function routingDetailText(result) {
  const status = routingStatusText(result)
  if (!status) return null

  const lines = ['Bicameral Design Drift', status, 'Advisory only. Bicameral remains the authority.']
  const limitations = Array.isArray(result?.limitations) ? result.limitations : []
  if (limitations.length) {
    lines.push('Limitation codes:')
    for (const limitation of limitations.slice(0, 8)) {
      const code = typeof limitation?.code === 'string' ? limitation.code : 'routing_limitation'
      lines.push(`- ${code}`)
    }
  }
  return lines.join('\n')
}
