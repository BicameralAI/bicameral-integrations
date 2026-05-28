# ADR-0003: Source Trust and Gating

**Date:** 2026-05-27  
**Status:** proposed  
**Level:** L1

## Problem

Sources differ sharply: Jira/Linear may be denoised enough for automatic candidate creation; Slack or meeting transcripts may be too noisy without manual gating.

## Decision

Adapters preserve source metadata and expose trust-tier configuration to the bot. Source trust can change candidate creation and review routing, but not canonical authority.

## Non-Goals

Integrations do not decide final policy outcomes.

## Consequences

Teams can tune noise without forking core governance logic.
