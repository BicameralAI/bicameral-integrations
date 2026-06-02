# Security Policy

## Reporting a Vulnerability

Please report security vulnerabilities to security@bicameral.ai. Do not disclose
suspected vulnerabilities publicly until maintainers have had a reasonable
opportunity to investigate and coordinate remediation.

## Supported Versions

This repository tracks source adapters and EM-safe mods before a tagged release
line exists. Security fixes are accepted against the default branch unless a
release branch is announced.

## Scope

Security reports are especially relevant when an adapter or mod could:

- Write canonical decision artifacts directly
- Bypass governance routing
- Collapse confidence or source-evidence surfaces
- Leak source payloads, tokens, secrets, or customer data
- Convert advisory signals into direct blocking authority

## Response

Maintainers will acknowledge reports, triage severity, and publish remediation
details when disclosure is appropriate.
