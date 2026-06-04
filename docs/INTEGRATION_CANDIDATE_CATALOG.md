# Bicameral Integration Candidate Catalog

Status: Draft
Owner: BicameralAI
Last updated: 2026-06-04

## 1. Purpose

This document defines a Bicameral-owned integration candidate catalog for `bicameral-integrations` and related Bicameral MCP adapter work.

The purpose of the catalog is to identify viable external systems whose APIs, webhooks, files, events, or exports can provide useful evidence, candidates, notifications, or governed action surfaces for Bicameral.

This catalog is product-agnostic. Adjacent tools and prior implementation work may be used to harvest candidate ideas, but they do not create runtime dependency, shared governance, shared authority, or strategic coupling.

## 2. Scope

In scope:

- Source control and code review systems
- Project and issue management systems
- Documentation and knowledge systems
- Communication and decision-capture systems
- Meeting and transcript systems
- Security and compliance evidence systems
- Observability and incident systems
- CRM, customer success, and support systems
- MCP and agent ecosystem integrations
- Data, analytics, and warehouse systems

Out of scope for initial connector implementation:

- Unverified third-party wrappers when official APIs exist
- Scraping-based connectors unless no viable API exists and risk is accepted
- Destructive write operations without explicit governance design
- Connectors that require broad customer PII access before a redaction model exists
- Agentic tool execution without trust scoring, scoped credentials, and approval gates

## 3. Bicameral Integration Principle

Bicameral integrations are evidence adapters, not state authorities.

An integration may:

- Fetch external records
- Receive webhook events
- Normalize external payloads into Bicameral-compatible structures
- Emit evidence records
- Emit candidate decisions, risks, drift alerts, or requirements
- Send notifications where allowed
- Propose external writes where explicitly supported

An integration must not:

- Own canonical Bicameral state
- Approve decisions silently
- Bypass Bicameral governance
- Treat external source claims as accepted truth
- Perform destructive writes without explicit policy
- Expand credential scope dynamically

## 4. Evaluation Criteria

Each integration candidate should be evaluated against the following criteria.

### Strategic fit

- Does the system contain decisions, requirements, implementation evidence, risk evidence, operational signals, or customer signals?
- Does it help Bicameral detect drift, preserve provenance, or improve accountability?
- Is it common enough across target users to justify first-party support?

### Technical viability

- Is there an official API?
- Are webhooks or change notifications available?
- Is authentication documented and maintainable?
- Are rate limits documented or inferable?
- Is there a supported SDK or OpenAPI spec?
- Can payloads be normalized without brittle scraping?

### Governance risk

- What data classes may be exposed?
- Can the connector be safely read-only?
- Are write actions reversible?
- Does the integration expose shell, filesystem, browser, database, or production-system control?
- Can credentials be scoped narrowly?
- Can events be audited and replayed?

### Maintenance risk

- How frequently does the provider change API behavior?
- Are versioned APIs available?
- Are webhook payloads stable?
- Is there a changelog?
- Is there an enterprise support path or community maintenance signal?

## 5. Priority Legend

- P0: Foundational. Should be supported early.
- P1: High value. Should be included after foundation stabilizes.
- P2: Valuable but situational.
- P3: Candidate only. Requires demand signal or special use case.
- Deferred: Not recommended until governance, security, or demand improves.

## 6. Candidate Catalog by Category

### 6.1 Source Control and Code Review

| Integration | Priority | Bicameral value | Initial mode | Default trust tier | Notes |
|---|---:|---|---|---|---|
| GitHub | P0 | Issues, PRs, commits, reviews, checks, security findings, provenance | Read-first, webhook ingest, proposed write later | T1/T3 | Highest priority source-control adapter. |
| GitLab | P1 | Merge requests, issues, pipelines, code review evidence | Read-first, webhook ingest | T1/T3 | Important for self-hosted and enterprise teams. |
| Bitbucket Cloud | P2 | Pull requests, commits, pipelines | Read-first, webhook ingest | T1/T3 | Useful for Atlassian-heavy teams. |
| Azure DevOps Repos | P2 | Repos, PRs, work items, build/release data | Read-first, webhook ingest | T1/T3 | Valuable in Microsoft enterprise environments. |
| Continue (continue.dev) | P1 | Developer-AI interaction evidence: chat/edit/autocomplete outcomes, model+prompt provenance | Read-only, passive file import (dev-data JSONL) | T0 | Schema-versioned dev-data (`level: noCode` redaction lever). No public read API. |
| Aider (aider.chat) | P1 | Developer-AI implementation provenance via attributed git commits | Read-only, passive git import | T0 | Deterministic `(aider)` attribution is the stable surface; unversioned transcript deferred. |

### 6.2 Project and Issue Management

| Integration | Priority | Bicameral value | Initial mode | Default trust tier | Notes |
|---|---:|---|---|---|---|
| Jira Cloud | P0 | Tickets, epics, change intent, acceptance criteria, issue history | Read-first, webhook ingest | T1/T3 | Enterprise planning anchor. |
| Linear | P0 | High-signal issues, roadmaps, comments, project updates | Read-first, webhook ingest | T1/T3 | Strong early adapter candidate. |
| Azure Boards | P2 | Work items and enterprise delivery planning | Read-first | T1/T3 | Good complement to Azure DevOps. |
| Asana | P2 | Cross-functional task and project planning | Read-first, webhook ingest | T1/T3 | Good for non-engineering workflows. |
| ClickUp | P2 | Task/project signals for broad SMB workflows | Read-first, webhook ingest | T1/T3 | Broad but payload normalization may be noisy. |
| Trello | P3 | Lightweight task/board state | Read-first, webhook ingest | T1/T3 | Useful for small teams, lower governance density. |

### 6.3 Documentation and Knowledge Systems

| Integration | Priority | Bicameral value | Initial mode | Default trust tier | Notes |
|---|---:|---|---|---|---|
| Notion | P0 | Specs, decisions, roadmaps, lightweight knowledge base | Read-first, webhook ingest | T1/T3 | Strong early candidate because Notion webhooks now exist. |
| Confluence Cloud | P1 | Enterprise docs, RFCs, architecture records, runbooks | Read-first, webhook ingest | T1/T3 | Important for Atlassian shops. |
| Google Drive / Docs | P1 | Shared docs, specs, meeting notes, artifacts | Read-first, push notifications | T1/T3 | Requires stale-state handling and careful permissions. |
| Microsoft SharePoint / OneDrive | P1 | Enterprise documents and knowledge base | Read-first, Graph change notifications | T1/T3 | Important Microsoft workspace target. |
| Dropbox | P3 | File artifact source | Read-first | T1 | Useful but less decision-rich than Docs/SharePoint. |

### 6.4 Communication and Decision Capture

| Integration | Priority | Bicameral value | Initial mode | Default trust tier | Notes |
|---|---:|---|---|---|---|
| Slack | P0 | Decision capture, notifications, approval routing | Notify first, ingest later | T2/T3 | Start with outbound notifications, add ingestion carefully. |
| Microsoft Teams | P1 | Enterprise notifications and collaboration context | Notify first, Graph ingest later | T2/T3 | Use Graph, avoid legacy connector assumptions. |
| Gmail | P2 | Support/customer/project email evidence | Read-only, redacted ingest | T1/T5 | Sensitive. Requires PII controls. |
| Outlook / Microsoft 365 Mail | P2 | Enterprise email evidence | Read-only, Graph notifications | T1/T5 | Sensitive. Requires tenant and consent controls. |
| Discord | P3 | Community/project decision capture | Notify first | T2/T3 | Useful for OSS/community workflows, less enterprise priority. |

### 6.5 Meetings and Transcripts

| Integration | Priority | Bicameral value | Initial mode | Default trust tier | Notes |
|---|---:|---|---|---|---|
| Zoom | P1 | Meeting metadata, recordings, transcripts, webinar events | Event ingest, transcript ingest where permitted | T1/T5 | High value when transcript governance exists. |
| Google Calendar / Meet artifacts | P2 | Meeting metadata, Drive artifacts, decision correlation | Metadata-first | T1/T3 | Meet artifacts often route through Drive/Calendar. |
| Microsoft Teams meeting artifacts | P2 | Meeting metadata and transcripts in Microsoft environments | Metadata-first | T1/T5 | Govern through Graph and tenant controls. |
| Otter.ai | P3 | Transcript evidence | Read-first if API viable | T1/T5 | Sensitive; validate API maturity. |
| Fireflies.ai | P3 | Transcript evidence | Read-first if API viable | T1/T5 | Sensitive; validate API maturity. |

### 6.6 Security and Compliance Evidence

| Integration | Priority | Bicameral value | Initial mode | Default trust tier | Notes |
|---|---:|---|---|---|---|
| SARIF 2.1.0 | P0 | Standardized static-analysis evidence | File ingest | T0 | Foundational security evidence format. |
| GitHub Code Scanning / CodeQL | P0 | Code security findings tied to repos and commits | API ingest | T1 | Strong GitHub-native security signal. |
| Semgrep | P1 | SAST, SCA, secrets, custom rule findings | API/file ingest | T1/T3 | Strong practical scanning integration. |
| Snyk | P1 | Dependency/container/code vulnerability findings | API/webhook ingest | T1/T3 | Webhooks currently require beta-awareness. |
| Dependabot | P1 | Dependency alerts and update PRs | GitHub API ingest | T1 | Usually captured through GitHub. |
| Trivy | P2 | Container, filesystem, SBOM, IaC scanning | File/CI ingest | T0/T1 | Good local and CI evidence source. |
| OSV | P2 | Vulnerability lookup and package version evidence | API lookup | T1 | Useful for dependency risk enrichment. |
| OWASP Dependency-Track | P2 | SBOM and component risk tracking | API/webhook ingest | T1/T3 | Strong compliance/security pipeline candidate. |

### 6.7 Observability and Incident Systems

| Integration | Priority | Bicameral value | Initial mode | Default trust tier | Notes |
|---|---:|---|---|---|---|
| Sentry | P1 | Runtime error correlation to changes and decisions | Webhook/API ingest | T1/T3 | Strong regression and impact evidence. |
| Datadog | P1 | Monitors, metrics, logs, events, incidents | Webhook/API ingest | T1/T3 | High enterprise value. |
| PagerDuty | P1 | Incidents, escalation history, operational impact | Webhook/API ingest | T1/T3 | Strong operational accountability signal. |
| New Relic | P2 | Alert and observability context | Notification/API ingest | T1/T3 | Useful where New Relic is primary APM. |
| Grafana | P2 | Alerts, dashboards, incident context | Webhook/API ingest | T1/T3 | Strong OSS/infra signal. |
| Prometheus Alertmanager | P2 | Alert stream evidence | Webhook ingest | T1 | Good low-level infra signal. |
| Opsgenie | P2 | Incident and alert workflows | Webhook/API ingest | T1/T3 | Atlassian ecosystem fit. |

### 6.8 CRM, Customer Success, and Support Systems

| Integration | Priority | Bicameral value | Initial mode | Default trust tier | Notes |
|---|---:|---|---|---|---|
| Salesforce | P2 | Account/customer context, customer impact evidence | Read-only first | T1/T5 | High PII and business sensitivity. |
| HubSpot | P2 | Customer lifecycle, support and marketing events | Read/event ingest | T1/T5 | Useful SMB/mid-market customer context. |
| Zendesk | P2 | Support tickets, customer issues, escalations | Read-first, webhook ingest | T1/T5 | Strong customer evidence source. |
| Intercom | P2 | Customer conversations and support signals | Read-first | T1/T5 | Sensitive, useful for customer-facing products. |
| Help Scout | P3 | Support tickets and conversations | Read-first | T1/T5 | Simpler support target. |
| Gainsight | P3 | Customer success health and churn signals | Read-first | T1/T5 | Enterprise CS use case. |
| ChurnZero | P3 | Customer success usage and health signals | Read-first | T1/T5 | CS-specific, useful when customer lifecycle is central. |

### 6.9 MCP and Agent Ecosystem

| Integration | Priority | Bicameral value | Initial mode | Default trust tier | Notes |
|---|---:|---|---|---|---|
| MCP Registry | P0 | MCP server discovery, scoring, allowlist support | Read-only scoring | T1 | Foundational MCP ecosystem target. |
| GitHub MCP Server | P0 | Repo/issue/PR access through MCP | Governed MCP review | T3/T5 | High value and high authority surface. |
| Filesystem MCP servers | P1 | Local file access and workspace evidence | Policy audit first | T3/T5 | Requires strict path and permission controls. |
| Database MCP servers | P1 | Database inspection and evidence | Policy audit first | T3/T5 | High data sensitivity. |
| Browser automation MCP servers | P2 | Web-based workflow evidence/action | Policy audit first | T3/T5 | High risk due to session access and side effects. |
| IDE coding agents | P2 | Agent intent, changes, and tool use | Observe first | T3/T5 | Adapter should collect run evidence, not grant authority. |

### 6.10 Data and Analytics Systems

| Integration | Priority | Bicameral value | Initial mode | Default trust tier | Notes |
|---|---:|---|---|---|---|
| PostHog | P2 | Product usage, events, feature adoption | Read-first | T1/T5 | Useful for product/customer impact. |
| GA4 | P2 | Marketing and site analytics | Read-first | T1/T5 | Useful at aggregate level. |
| BigQuery | P2 | Warehouse-backed evidence and analytics | Read-first | T1/T5 | Strong for mature data teams. |
| Snowflake | P2 | Enterprise data warehouse evidence | Read-first | T1/T5 | High governance burden. |
| Supabase | P2 | App database/events for smaller teams | Read-first | T1/T5 | Useful for product telemetry and internal apps. |
| Segment | P3 | Event pipeline context | Read-first | T1/T5 | Useful but may duplicate analytics connectors. |
| Mixpanel | P3 | Product analytics and funnel signals | Read-first | T1/T5 | Useful when product analytics are central. |

## 7. Adapter Readiness Matrix

| Readiness level | Meaning |
|---|---|
| Candidate | Viable target identified, not yet researched in detail. |
| Researched | Official docs and auth model recorded. |
| Contracted | Bicameral payload mappings drafted. |
| Prototype | Adapter can ingest sample payloads. |
| Beta | Adapter works with real credentials and limited users. |
| Stable | Adapter has tests, docs, version handling, and governance controls. |

## 8. Initial Roadmap Recommendation

### Phase 1: Foundation

- GitHub
- Linear
- Jira Cloud
- Slack notification
- Notion
- SARIF
- MCP Registry

### Phase 2: Security and operational evidence

- GitHub Code Scanning / CodeQL
- Semgrep
- Sentry
- Datadog
- PagerDuty
- Google Drive / Docs
- Microsoft Graph notifications

### Phase 3: Customer and enterprise context

- Salesforce
- HubSpot
- Zendesk
- Confluence
- Zoom
- SharePoint / OneDrive

### Phase 4: High-risk governed action surfaces

- GitHub proposed writes
- Jira proposed writes
- Linear proposed writes
- MCP server policy audits
- Agent run evidence adapters
- Database MCP governance
- Browser automation MCP governance

## 9. Excluded or Deferred Integrations

Defer integrations that require:

- Broad OAuth scopes before a consent and scope review process exists
- Destructive writes as the primary value proposition
- Unstructured scraping of authenticated apps
- Ingestion of full email/chat history without redaction
- Live agentic action without policy enforcement
- Unofficial APIs where official APIs exist

## 10. Related Tooling Candidate Harvesting

Bicameral may harvest integration candidates from adjacent tools, internal prototypes, open-source projects, customer workflows, MCP ecosystem patterns, and prior implementation work.

Candidate harvesting does not imply runtime dependency, shared authority, shared governance, or product coupling.

All harvested candidates must be independently evaluated against Bicameral's adapter contract, trust tier model, source documentation, maintenance burden, and security posture.
