# ADR-0001: Adapters Emit Candidates and Evidence

**Date:** 2026-05-27  
**Status:** proposed  
**Level:** L1

## Problem

Integrations touch external systems with different noise levels and trust properties. Letting an adapter write canonical decisions would make source-specific code a governance authority.

## Decision

Adapters emit protocol-shaped candidates, evidence, hints, signals, and advisories into the `bicameral-bot` gateway. They never write canonical event store artifacts directly.

## Non-Goals

This ADR does not define bot governance policy or storage adapter behavior.

## Consequences

Adapters stay inspectable and swappable. The bot remains the only path from edge evidence to canonical materialization.
