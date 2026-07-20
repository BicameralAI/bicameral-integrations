# Release Manifest Adoption: Bicameral Integrations

Status: descriptor CI implemented
Related Factory blueprint: https://github.com/BicameralAI/bicameral-factory/pull/290

## Purpose

Defines how integration artifacts participate in incremental cross-repository release evidence without forcing unrelated hosted-dashboard topology runs.

## Integration-owned release inputs

Each integration build/configuration release emits immutable provenance and an interface fingerprint for adapter artifact/version, connector configuration schema/compatibility policy, typed evidence/candidate payload contract delivered to Bot, and relevant security/runtime configuration. An adapter does not obtain Decision Ledger authority by participating in a release manifest.

## Journey closure

Integration adapter artifact/config + Bot integration-ingress interface + Bot MCP interface + MCP artifact/protocol.

If an integration changes, this closure is revalidated with pinned Bot and MCP artifacts. Bot-to-Cloud evidence is reusable only when its independent closure is identical. Paths, labels, and claims that Bot/Cloud were not edited are insufficient.

## Delivery gates

1. Integration CI emits deterministic interface fingerprint and provenance.
2. Release assembly records the integration closure.
3. A real-process Integration-to-Bot-to-MCP receipt is bound to that closure before a manifest requiring this journey is promoted.
4. Missing dependency edges fail closed.

## Authority boundaries

- Adapters emit evidence, candidates, hints, and proposed actions only under existing trust-tier rules.
- Release records are operational evidence, not Decision, signoff, compliance, or source authority.
- This adds no direct Cloud dependency to Integrations.

## Non-goals

No Bot/Cloud release implementation or connector lifecycle state. Descriptor CI is component provenance, not terminal journey evidence.
