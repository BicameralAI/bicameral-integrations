# Bicameral Integrations

Open-source adapters and EM-safe mods for Bicameral.

This repo contains source connectors and lightweight domain-specific extensions that emit typed Bicameral objects. Integrations are expressive at the edge, but they do not own canonical authority.

## Scope

Examples:

- Jira issue adapter
- Linear issue adapter
- Slack thread adapter
- Notion transcript adapter
- GitHub PR/issue adapter
- support/email adapter
- meeting transcript adapter
- EM-safe mod examples

## Safety rule

Integrations and mods emit candidates, evidence, routing hints, dependency signals, and advisory governance results. They never write `.bicameral/decisions/*.yaml` directly and never silently approve/block work.
