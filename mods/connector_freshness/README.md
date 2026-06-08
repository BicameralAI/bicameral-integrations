# Connector Freshness Mod

Status: Scoped

Advisory mod for detecting stale provider assumptions in connector docs,
fixtures, auth notes, references, and parser scope.

## Scope

- Provider API version changes and deprecations.
- Missing or stale `references.md` and `auth.md` links.
- Rate-limit, pagination, and retry assumptions that are undocumented.
- Webhook schema drift and unknown event payloads.
- Connector docs that imply live support where only parse fixtures exist.

## Outputs

- `source_evidence_annotation`
- `routing_hint`
- `advisory_governance_result`

## Boundary

This mod can flag freshness risk and route connector review. It must not fetch
providers automatically or expand credentials.

## References

See [references.md](references.md).
