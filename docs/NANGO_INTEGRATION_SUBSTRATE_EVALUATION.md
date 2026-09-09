# Nango Integration Substrate Evaluation

**Status:** Exploration required

**Decision owner:** Bicameral Integrations architecture / Product

**Tracking issue:** #304

**Decision outcome:** Pending (`adopt`, `adopt_bounded`, `defer`, or `reject`)

## Executive summary

Bicameral should evaluate Nango before investing further in broad bespoke connector-runtime infrastructure.

The opportunity is not to replace Bicameral Integrations as a product boundary. The opportunity is to stop rebuilding commodity integration mechanics where a mature substrate can provide them, while preserving the parts that are Bicameral-specific and governance-sensitive.

A likely target boundary is:

```text
Provider API
  -> Nango acquisition substrate
     - auth / credential lifecycle
     - proxy
     - sync / polling
     - webhook runtime
     - retries / rate limits
     - connection operations
  -> thin Bicameral provider mapping
  -> provider minimization + deterministic redaction
  -> canonical provider-neutral Observation
  -> universal adapter + advisories
  -> authority-stripped ExternalIngestEnvelope
  -> GatewaySink
  -> Bicameral daemon
```

This is an evaluation, not an adoption decision. No existing Bicameral evidence, redaction, authority, or daemon boundary should be weakened to accommodate Nango.

## Why evaluate this now

The current Integrations architecture deliberately centralizes source-specific acquisition and normalization before delivering neutral records to the daemon. That is still the right Product boundary.

However, implementation responsibility currently spans two very different categories:

1. **commodity integration-runtime mechanics**: provider authentication, credential lifecycle, API calls, cursors, polling, webhooks, retries, rate limits, connection state, and runtime operations;
2. **Bicameral-specific semantics and governance**: evidence identity, field minimization, deterministic redaction, canonical Observation semantics, advisory classification, provenance, authority stripping, and GatewaySink delivery.

Nango is designed specifically around the first category. Its current product describes managed authentication, token refresh, multi-tenant connections, API execution, scaling, retries, rate-limit handling, integration functions, syncs, webhooks, and operational observability across a large provider catalog.

If that substrate is a good fit, continuing to broaden our own generic auth/sync/webhook framework first would be sunk engineering effort with little Bicameral differentiation.

## Current Bicameral responsibilities and candidate disposition

| Responsibility | Candidate disposition | Rationale |
| --- | --- | --- |
| Provider OAuth / API-key / credential acquisition | `replace_candidate` | Core Nango capability; high commodity cost in bespoke implementations. |
| Token refresh / credential lifecycle | `replace_candidate` | Strong candidate if custody and tenancy controls satisfy Bicameral requirements. |
| Multi-tenant provider connection management | `replace_candidate` | Nango's connection model may substantially simplify this layer. |
| Provider API proxy | `replace_candidate` | Useful where we retain Bicameral mapping/redaction downstream. |
| Scheduled polling / incremental sync runtime | `depends_on_deployment_model` | Available in the full Nango runtime; free self-hosting is more limited. |
| Provider webhook runtime | `depends_on_deployment_model` | Full-runtime feature; authenticity/replay semantics must be verified. |
| Retry / backoff / rate-limit mechanics | `replace_candidate` | Commodity runtime capability, provided semantics are observable and fail safely. |
| Connection health / integration runtime observability | `replace_candidate` | Could remove bespoke operational state, but must not become evidence authority. |
| Provider-specific response mapping | `retain` | This is where provider facts become Bicameral semantic inputs. |
| Source identity / source-scope verification | `retain` | Required provenance boundary. |
| Provider field minimization | `retain` | Bicameral privacy/security policy, not transport plumbing. |
| Deterministic redaction | `retain` | Must remain independently governed and testable. |
| Canonical `Observation` contract | `retain` | Keeps Bicameral source-neutral and prevents Nango-shaped Product contracts. |
| Advisory / heuristic semantics | `retain` | Bicameral-defined non-authoritative inference boundary. |
| Authority stripping | `retain` | External integrations must never acquire Product/Decision authority. |
| Transformation / evidence provenance | `retain` | Needed to explain how external records became Bicameral observations. |
| `GatewaySink` / `/api/v1/external-ingest` | `retain` | Stable daemon boundary and replacement seam. |
| Product / Decision interpretation | `retain` in daemon/Product | Explicitly outside integration-substrate authority. |

## Nango facts that materially affect the decision

As of this evaluation, Nango's public repository describes support for 900+ APIs and a runtime covering authentication, execution, scaling, retries, and rate-limit handling. Integrations are expressed as TypeScript functions, and Nango supports API/CLI-driven workflows.

Nango describes itself as open source, but its repository is licensed under the **Elastic License 2.0 (ELv2)**. This is not equivalent to adopting a permissive MIT/Apache dependency. ELv2 allows use, modification, distribution, and derivative works subject to restrictions, including restrictions around providing substantial Nango functionality as a hosted/managed service. Legal/commercial fit must therefore be part of the architecture decision rather than an implementation afterthought.

The deployment model also matters:

- **Nango Cloud** provides the full managed runtime.
- **Enterprise self-hosted** provides the full runtime on customer-controlled infrastructure according to Nango's commercial offering.
- **Free self-hosted** is a limited feature set focused on authentication and proxying rather than the complete functions/sync/webhook runtime.

Sources to re-verify at decision time:

- https://github.com/NangoHQ/nango
- https://nango.dev/
- https://nango.dev/pricing
- https://docs.nango.dev/

These are current-product facts, not permanent architectural guarantees. The final decision must pin the exact license/version/commercial terms evaluated.

## Options

### Option A: Nango Cloud as the full acquisition runtime

Nango owns auth, credential lifecycle, execution, syncs, actions, webhooks, retries, rate limits, and operational runtime. Bicameral begins at the thin mapping/minimization boundary.

**Potential advantages**

- largest immediate reduction in bespoke infrastructure;
- quickest path to broad provider coverage;
- lower operational burden;
- existing observability and connection management;
- likely best route for proving whether the integration substrate idea is sound.

**Primary risks / questions**

- external credential custody and data-processing implications;
- data residency and customer security expectations;
- dependence on Nango Cloud availability and pricing;
- ELv2/commercial terms;
- ensuring logs/runtime data do not retain fields Bicameral would otherwise minimize;
- ensuring Nango records never become authoritative Bicameral evidence by implication.

### Option B: Enterprise self-hosted full Nango runtime

Use the full Nango platform but operate it inside Bicameral-controlled infrastructure.

**Potential advantages**

- keeps the full runtime while improving infrastructure/data control;
- may align better with enterprise design partners and compliance requirements;
- retains a known platform instead of rebuilding the same mechanics internally.

**Primary risks / questions**

- commercial licensing;
- significant infrastructure footprint and operational burden;
- version upgrades and platform maintenance become Bicameral responsibilities;
- may be premature for alpha-scale usage.

### Option C: Free self-hosted Nango for auth/proxy only

Use Nango for connection establishment, token lifecycle, and proxying, while retaining Bicameral polling/webhook/scheduling infrastructure.

**Potential advantages**

- removes one of the hardest/least differentiated layers, OAuth and credential handling;
- narrower adoption surface;
- lower data-runtime dependency on Nango;
- potentially easier replacement seam.

**Primary risks / questions**

- preserves substantial bespoke runtime work;
- may result in an awkward split where Bicameral owns exactly the operational machinery Nango's full runtime already solves;
- must verify free self-host feature and license boundaries at the selected version.

### Option D: Continue bespoke Bicameral runtime

Retain the current architecture and implement provider auth, polling/webhooks, retries, rate limits, and connection lifecycle internally.

**Potential advantages**

- maximum implementation and data control;
- no Nango commercial/platform dependency;
- direct fit with existing Python runtime decisions.

**Primary risks / questions**

- highest engineering and maintenance cost;
- broad provider API churn becomes our problem;
- significant effort does not differentiate Bicameral;
- likely delays user-visible integration coverage.

## Security, privacy, and governance requirements

Any Nango-backed design must preserve these invariants.

### Credential custody

Document exactly where credentials and refresh tokens live, who can decrypt/use them, and what Bicameral components can access them. No integration runtime may expose reusable provider credentials to the daemon or UI merely for convenience.

### Minimize before Bicameral ingestion

Provider responses must pass through Bicameral-owned scope checking, minimization, and deterministic redaction before they become canonical Observations or reach the daemon.

If Nango Cloud processes raw provider data first, that is an explicit third-party processing boundary and must be evaluated accordingly.

### Provider authenticity and replay

For webhook/event paths, verify how Nango validates provider signatures, handles replay/duplication, exposes delivery identity, and represents retries. Bicameral must retain enough provenance to prove which source event produced an Observation.

### Authority separation

Nango may report connection state, execution state, provider responses, and runtime failures. None of those states grant Product, Decision, release, evidence-acceptance, or governance authority.

### Fail closed where integrity matters

A missing/ambiguous source identity, credential scope mismatch, redaction failure, malformed event, or unprovable replay identity must not silently become a trusted Observation.

## Integration contract / replacement seam

Bicameral should not let Nango-specific concepts leak past the acquisition adapter.

A Nango-backed adapter should translate into the same provider-neutral contracts that a bespoke adapter would produce. The daemon should not know or care whether a record arrived through:

- Nango Cloud;
- Nango self-hosted;
- a direct provider adapter;
- a future replacement substrate.

This is the most important architectural hedge. Nango can replace plumbing without becoming the shape of Bicameral.

## Tracer bullet 1: GitHub read-only acquisition

### Goal

Prove the normal Nango-backed acquisition path against a provider Bicameral already understands well.

### Candidate flow

```text
GitHub connection in Nango
  -> read-only GitHub issue / PR acquisition
  -> Bicameral GitHub mapper
  -> source-scope verification
  -> minimization/redaction
  -> Observation
  -> universal adapter
  -> ExternalIngestEnvelope
  -> GatewaySink
```

### Required positive evidence

- exact account/repository connection identity;
- least-privilege requested scopes;
- repeatable acquisition of a known GitHub record;
- deterministic normalized Observation;
- redacted/minimized fields demonstrated;
- duplicate acquisition is idempotent or explicitly represented;
- GatewaySink accepts the same downstream contract as the current adapter path.

### Required negative evidence

- revoked/expired connection;
- insufficient GitHub scope;
- rate-limited request;
- missing/deleted record;
- malformed/unexpected provider payload;
- duplicate/replayed event;
- redaction failure.

No happy-path-only demo is sufficient.

## Tracer bullet 2: Google Drive OAuth-heavy acquisition

### Goal

Measure the engineering burden Nango removes on an OAuth/refresh-sensitive provider rather than extrapolating from GitHub.

### Candidate flow

```text
Google Drive connection in Nango
  -> least-privilege file metadata/content acquisition
  -> Bicameral Drive mapper
  -> source-scope verification
  -> minimization/redaction
  -> Observation
  -> GatewaySink
```

### Required positive evidence

- user authorization through the intended tenant/account;
- exact OAuth scopes recorded;
- token refresh without Bicameral custom refresh code;
- stable connection identity across refresh;
- bounded read of a known Drive object;
- deterministic downstream Observation;
- no raw credential reaches Bicameral daemon/Product surfaces.

### Required negative evidence

- revoked consent;
- refresh failure;
- tenant/account mismatch;
- inaccessible/deleted file;
- changed scopes;
- provider quota/rate limit;
- Nango outage/runtime failure;
- sensitive document content rejected or redacted according to policy.

## Factory / roadmap implications

Nango adoption would change implementation assumptions, not the intended authority architecture.

At minimum, reconcile the following Factory-era assumptions before implementation:

- older alpha platform decisions binding `bicameral-integrations` to a Python 3.13+ stdlib-only runtime;
- D1/D2 execution plans that assume Bicameral builds the complete connector acquisition/runtime substrate itself;
- terminal GitHub-to-reviewed-Decision journeys that require an actual Integrations acquisition path but should not care whether commodity acquisition mechanics are Nango-backed;
- strong-alpha connector scope, which should prioritize a small design-partner provider set rather than broad bespoke framework completeness.

Durable ingestion boundaries remain valid: Integrations produces provider-derived neutral evidence; the daemon/Product layer owns projection, Decision semantics, and authority.

## Recommended near-term constraint

Until this evaluation closes, avoid starting broad framework work for:

- generalized OAuth orchestration;
- generalized token-refresh infrastructure;
- generic polling scheduler expansion;
- generic webhook framework expansion;
- generalized rate-limit/retry abstractions;
- connection-health platform work.

Exceptions are bounded fixes required for an already-committed release or terminal product journey.

This is a stop-spending-before-the-build-vs-buy-decision constraint, not a freeze on Integrations product work.

## Evaluation sequence

1. Verify exact Nango license and current Cloud/self-host feature split.
2. Map current Bicameral runtime responsibilities to Nango capabilities using the disposition table above.
3. Price Cloud and Enterprise self-hosting at realistic alpha/design-partner usage.
4. Build the non-production GitHub tracer bullet.
5. Build or design-review the Google Drive OAuth tracer bullet.
6. Perform threat/privacy review of credential custody, raw provider data, logging, replay, and tenant isolation.
7. Confirm the downstream `Observation` and `GatewaySink` contracts remain Nango-independent.
8. Reconcile affected Factory architecture assumptions.
9. Record one decision: `adopt`, `adopt_bounded`, `defer`, or `reject`.
10. Only then authorize the first production implementation slice.

## Decision rubric

Prefer **adopt** or **adopt_bounded** when Nango demonstrably removes substantial commodity runtime work without weakening credential, privacy, provenance, replacement-seam, or authority requirements.

Prefer **defer** when the fit is promising but commercial/security/operational constraints cannot be closed before alpha.

Prefer **reject** when Nango forces Bicameral-specific contracts to become platform-shaped, materially weakens governance/privacy boundaries, or costs more to operate/contain than the engineering it removes.

## Non-goals

This evaluation does not:

- replace Bicameral's Observation schema;
- move redaction/governance authority to Nango;
- make Nango's unified models canonical Bicameral data models;
- authorize write-back integrations;
- authorize production credentials;
- require every provider to use Nango;
- require Nango Cloud over self-hosting;
- make connector breadth an alpha gate.

## Completion criteria

The evaluation is complete when issue #304 records one explicit decision with:

- selected deployment/runtime model;
- exact license/commercial basis;
- GitHub and Google Drive evidence;
- retained/replaced responsibility map;
- security/privacy findings;
- Factory planning reconciliations;
- first bounded implementation slice if adopted.