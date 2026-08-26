# Nango evaluation evidence, 2026-08-26

**Status:** Research evidence for #304 / draft PR #305

**Purpose:** Ground the Nango substrate decision in current Bicameral Integrations contracts and current Nango product documentation. This document does not authorize adoption, production credentials, provider activation, or migration.

## Executive finding

The current evidence supports a serious `adopt_bounded` hypothesis for evaluation.

Bicameral does not need Nango to replace its provider-neutral evidence model, discovery semantics, redaction, authority boundaries, or daemon delivery seam. Those existing contracts are valuable and should remain stable.

Nango is potentially valuable behind those contracts because it directly overlaps the least differentiated part of the current operator-runtime responsibility: provider authentication, token lifecycle, connection management, proxying, incremental sync execution, webhook handling, retries, rate limits, and runtime observability.

The architectural question is therefore narrower than "replace Bicameral Integrations with Nango":

> Can Nango become a replaceable acquisition/runtime substrate behind Bicameral-owned provider mapping, screening, Observation, provenance, and GatewaySink contracts?

Current evidence says this is plausible enough that broad new bespoke acquisition-runtime framework work should wait for the tracer decision.

## Current Bicameral ground to preserve

### Operator runtime is intentionally a seam

`runtime/README.md` states that Bicameral Integrations remains a library rather than a server. The operator host currently owns the HTTP receiver / cron boundary and wires connector execution into `deliver_webhook`, `poll`, and `GatewaySink`.

The existing runtime owns or exposes mechanics for:

- operator-provided secret resolution;
- authenticated live polling;
- pagination;
- provider-specific polling specifications;
- webhook delivery;
- normalized emission;
- exact gateway capability matching;
- fail-closed delivery to `/api/v2/external-ingest`.

This is a strong replacement seam. A Nango-backed acquisition implementation does not require changing `GatewaySink` or making the daemon understand Nango.

### Google Drive demonstrates the missing commodity-runtime problem

The current runtime specifically records Google Drive as deferred from the generic poll shape because it requires OAuth and per-resource fetching. That is precisely the class of provider lifecycle Nango is designed to handle.

This makes Google Drive an especially valuable tracer. It tests whether Nango removes real engineering complexity rather than merely replacing already-simple API-key polling.

### Provider acquisition is already provider-neutral

ADR-0017 defines discovery/fetch/readiness as provider-neutral contracts returning descriptors, access verdicts, and screened provider facts rather than Bicameral authority objects.

Important boundaries already exist and should survive any Nango adoption:

- discovery returns provider facts, not Product authority;
- fetched content still passes the same Bicameral screening/normalization funnel;
- provider writes remain outside the discovery authority boundary;
- resource descriptors remain provider-neutral;
- the daemon is not coupled to provider authentication mechanics;
- provider acquisition may change implementation without changing canonical Bicameral meaning.

This is the main architectural reason Nango can be evaluated as a substrate rather than a product-model migration.

## Current Nango facts verified for this evaluation

The following facts were re-verified against Nango's current public documentation on 2026-08-26.

### Provider breadth

Nango currently advertises 900+ supported APIs. Its catalog includes providers directly relevant to Bicameral's plausible alpha and post-alpha integration surface, including GitHub App, Google Drive, Slack, Gmail, Google Calendar, Microsoft Teams, Jira, Linear, Notion, ServiceNow, SharePoint, Salesforce, and others.

Sources:

- https://nango.dev/api-integrations
- https://github.com/NangoHQ/nango

### Runtime scope

Nango describes its full runtime as covering managed authentication, credential/token refresh, actions, syncs, webhooks, execution, retries, rate-limit handling, connection operations, and observability.

Nango's GitHub integration guidance demonstrates a representative combination of:

- GitHub App / OAuth authorization;
- durable issue and PR syncs;
- signature-verified GitHub webhooks;
- actions;
- typed MCP exposure.

This is direct overlap with infrastructure Bicameral should avoid rebuilding unless our contracts require materially different semantics.

Sources:

- https://nango.dev/
- https://nango.dev/blog/build-a-github-api-integration-for-ai-agents

### Free self-hosting is not the full runtime

Nango's current self-hosting documentation distinguishes:

**Free self-hosted**

- Auth: yes
- Proxy: yes
- Auth/proxy observability: yes
- Functions: no
- Webhooks: no
- MCP server: no
- full runtime observability: no

**Enterprise self-hosted / Nango Cloud**

- full functions/runtime;
- webhooks;
- full observability;
- additional enterprise controls and support.

Enterprise self-hosting requires an Enterprise subscription and uses a materially larger infrastructure footprint including Node services, Postgres, Redis, object storage, and Elasticsearch.

Source:

- https://nango.dev/docs/guides/platform/self-hosting

### Self-hosted credential security requires deliberate configuration

Nango's self-hosting guide explicitly states that sensitive credential encryption must be configured with an encryption key and warns that without the key credentials are stored unencrypted. It also states key rotation is not currently supported by simply changing the key because existing credentials would become undecryptable.

This is a material security/operations consideration for any self-hosted option and must be included in threat review and runbook design.

Source:

- https://nango.dev/docs/guides/platform/self-hosting

### Google Drive still requires Bicameral-owned Google application decisions

Nango can manage the OAuth connection and subsequent token lifecycle, but it does not remove Google's application-registration and production-verification requirements.

Current Nango documentation requires an application to register a Google OAuth client, configure scopes and Nango's callback URL, and complete Google's required verification/security review for restricted scopes before production use. `drive.file` is identified as a narrower non-restricted alternative for user-selected files, while broader Drive scopes may require verification.

Therefore Nango can simplify runtime credential/token mechanics, but it does not eliminate the current external Google provisioning dependency identified in the strong-alpha readiness work.

Sources:

- https://nango.dev/docs/api-integrations/google-drive/how-to-register-your-own-google-drive-api-oauth-app
- https://nango.dev/docs/api-integrations/google-drive

### Google Drive has an existing Nango sync path suitable for the tracer

Nango currently documents pre-built Google Drive file/folder sync behavior with incremental updates and a production-shaped sample using OAuth, Google Picker, syncs, webhooks, and file access.

This creates a useful experiment against Bicameral ADR-0017: use Nango to obtain the provider connection and selected-file acquisition, but translate the result into the existing Bicameral provider descriptor / Observation / screening path instead of adopting Nango records as canonical Bicameral models.

Source:

- https://nango.dev/docs/api-integrations/google-drive/how-to-use-google-drive-files-sync

### License model

Nango's repository describes the product as available under the Elastic License and distinguishes the limited free self-hosted edition from Cloud and Enterprise Self-Hosted feature access.

The final decision must pin the exact evaluated license text and commercial terms. Bicameral must not treat the word "open source" as equivalent to permissive dependency licensing.

Source:

- https://github.com/NangoHQ/nango

## Candidate architecture after this evidence pass

The strongest current candidate is:

```text
provider
  -> Nango connection/auth/acquisition runtime
  -> Bicameral acquisition adapter
       - map connection/resource identity to SourceRef
       - validate expected provider/account/resource scope
       - convert provider result to existing descriptor or Observation
  -> existing Bicameral screening/minimization
  -> existing normalize / AdapterEmission path
  -> existing GatewaySink
  -> Bicameral daemon
```

Nango identifiers may be retained as provenance metadata where useful, but they must not become canonical Product identity or the only way to reconstruct Bicameral evidence meaning.

## What could likely be retired or avoided if the tracer succeeds

The following should be treated as probable replacement candidates rather than default future implementation work:

- generalized OAuth orchestration inside the Integrations operator host;
- generalized token-refresh infrastructure;
- homegrown multi-tenant connection lifecycle management;
- generic polling scheduler infrastructure;
- generic webhook receiver/runtime framework;
- generic provider retry/backoff/rate-limit orchestration;
- generic connection-health runtime;
- provider-specific token-storage conventions.

Existing bounded connector parsing, normalization, source semantics, redaction, fixtures, provenance, and Gateway delivery remain valuable.

## What Nango does not solve

Nango adoption would not remove responsibility for:

- choosing and registering provider applications;
- Google OAuth verification/security-review requirements;
- provider scope design and least privilege;
- deciding which provider resources Bicameral may ingest;
- Bicameral field minimization and sensitive-data screening;
- source authenticity/provenance semantics Bicameral needs downstream;
- canonical Observation and AdapterEmission meaning;
- Product/Decision authority separation;
- downstream daemon ingestion and acceptance;
- Bicameral-specific negative evidence and failure semantics;
- customer security/compliance review of a third-party Cloud processor if Nango Cloud is used.

## Tracer recommendation

### First tracer: GitHub read-only

Use Nango's GitHub App support to acquire a bounded issue/PR dataset from a test installation.

Success requires proving that the Nango-backed adapter emits the same Bicameral-owned downstream contract expected by the existing runtime and that revoked access, scope failure, duplicate acquisition, malformed provider data, rate limiting, and redaction failure remain visible and safe.

Do not expose Nango MCP directly to the Bicameral daemon as the tracer. That would test a different architecture and unnecessarily couple Product tooling to the substrate.

### Second tracer: Google Drive selected-file path

Prefer a least-privilege selected-file path first, with exact scopes documented. Measure:

- Google application setup still required;
- Nango-managed OAuth connection establishment;
- refresh behavior;
- stable account/connection identity;
- selected resource identity;
- translation into Bicameral `SourceRef` / descriptor / Observation semantics;
- downstream sensitive-content screening;
- revocation and refresh-failure behavior.

This tracer should answer whether Nango materially simplifies the exact Drive acquisition work that current Bicameral runtime documentation leaves deferred.

## Decision gates remaining

Before #304 can close, the following remain genuinely unresolved:

1. commercial pricing at expected design-partner volume;
2. Cloud data-processing and credential-custody acceptability;
3. exact ELv2/legal fit for Bicameral's intended distribution and service model;
4. whether GitHub and Google Drive tracer outputs can be translated cleanly without Nango concepts leaking downstream;
5. whether the full Cloud runtime or auth-only bounded adoption has the better alpha cost/complexity profile;
6. how a Nango-backed implementation coexists with existing direct connectors during migration and fallback;
7. exact Factory #285 reconciliation if a TypeScript/Nango runtime becomes part of the alpha architecture.

## Current recommendation

Do not adopt Nango into production yet.

Do treat `adopt_bounded` as the leading hypothesis and spend the next Integrations engineering effort on the two tracer bullets rather than on generalized bespoke acquisition infrastructure.

The existing Bicameral provider-neutral contracts make this unusually reversible. If Nango fails the tracer on security, licensing, cost, semantics, or operations, the downstream architecture remains intact and the current direct-connector path can continue.