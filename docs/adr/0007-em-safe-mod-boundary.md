# ADR-0007: EM-Safe Mod Boundary

**Date:** 2026-06-02  
**Status:** proposed  
**Level:** L1

## Problem

Engineering managers and domain owners need a way to add local extraction,
routing, ownership, dependency-risk, and security-review intelligence. Giving
those extensions direct authority over decisions, signoff, or compliance would
collapse Bicameral's governance boundary.

## Decision

EM-safe mods are advisory post-processors over adapter emissions.

Mods may emit:

- source evidence annotations;
- dependency or security signals;
- owner-lens hints;
- review routing hints;
- advisory governance results;
- suggested review questions.

Mods must not:

- write canonical decisions;
- approve signoff;
- resolve compliance;
- create direct blocking CI results;
- bypass governance policy;
- delete or mutate source evidence;
- collapse confidence into one opaque score.

Mods use a declarative manifest, fixture inputs, expected outputs, and
validation rules. The manifest records mod id, version, supported source types,
allowed outputs, confidence dimensions, audit preservation, and forbidden
actions.

## Consequences

Mods can raise recall and improve review routing without becoming policy
engines. This gives Bicameral a safe extension path for early customer-specific
workflow knowledge while keeping final authority in MCP governance.

