# ADR-0003: Source Adapters Are Open and Swappable

Status: accepted

Date: 2026-05-27

## Context

Customer evidence shows that the source of truth is already elsewhere: Jira for some teams, Linear for others, Slack or meetings for informal decisions, GitHub for implementation evidence, and support inboxes for customer signals.

## Decision

Adapters live in the public `bicameral-integrations` repo and target the shared `bicameral-protocol` contracts.

No adapter is privileged by the core. Each adapter produces typed candidates/evidence/signals into the daemon/gateway path.

## Consequences

Teams can inspect, patch, fork, or contribute integrations. Bicameral can meet each team’s operational substrate without centralizing all source access inside a closed hosted service.
