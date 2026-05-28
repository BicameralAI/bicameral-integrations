# ADR-0002: Mods Emit Evidence, Not Authority

Status: accepted

Date: 2026-05-27

## Context

EMs should be able to vibe-code lightweight domain-specific Bicameral mods, such as Jira dependency-risk detectors, security/SOC2 decision detectors, routing hints, or support-thread decision extractors.

These mods are valuable only if they cannot compromise the core architecture.

## Decision

Mods may emit:

- `DecisionCandidate`
- `DependencySignal`
- `BindingHint`
- `SourceEvidence`
- `ReviewCommand` suggestions
- advisory `GovernanceResult`

Mods may not:

- write canonical decision files directly
- approve or reject decisions
- mark compliance resolved
- create blocking CI results directly
- collapse extraction, binding, and compliance into one score
- bypass governance policy

## Consequences

Mod manifests must declare output types, review roles, confidence surfaces, source evidence preservation, and storage behavior. Manifest validation must reject canonical writes and silent authority creation.
