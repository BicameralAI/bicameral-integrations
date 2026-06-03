# ADR-0006: Active, Passive, and Webhook Modes

**Date:** 2026-06-02  
**Status:** proposed  
**Level:** L1

## Problem

Integrations enter Bicameral through different operational modes. A user can
paste a URL, a configured source can be polled, or an external provider can push
a webhook. These modes share normalization and evidence rules but differ in
auth, retries, replay defense, and cursor semantics.

## Decision

The integration architecture defines three mode interfaces:

- **Active fetch**: operator-initiated fetch for a URL or explicit source ref.
- **Passive polling**: configured source pull with a cursor and two-phase
  cursor confirmation.
- **Webhook handling**: provider push handling with verification, dedup, and
  event normalization.

Connectors may implement any subset of these modes. Source capabilities declare
which modes are supported, and the universal adapter consumes connector output
through the shared emission pipeline.

## Mode Rules

Active fetch:

- may raise provider/auth errors;
- must not write canonical state;
- returns connector observations that the universal adapter normalizes into
  emissions.

Passive polling:

- stages cursor advancement during pull;
- confirms the cursor only after downstream ingest succeeds;
- applies universal filters and quotas before emission where possible.

Webhook handling:

- verifies provider authenticity before trusting parsed fields;
- dedups after verification;
- treats permanent hard-gate refusals as non-retryable;
- returns retryable status only for transient failures.

## Consequences

GitHub, Google Drive, Jira, Slack, Notion, email, and meeting sources can share
one lifecycle model without pretending their provider protocols are identical.
Webhook connector handlers are recognized as higher-risk than read-only
connectors and should move from `bicameral-mcp` only after explicit conformance
tests exist.
