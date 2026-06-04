# Bicameral Integration Documentation Index

Status: Draft
Owner: BicameralAI
Last updated: 2026-06-04

## Purpose

This document tracks official documentation for integration candidates. The index should be treated as a living maintenance artifact. Each integration entry should be refreshed periodically because APIs and webhook systems drift, mutate, deprecate, or otherwise behave like tiny bureaucracies with JSON payloads.

Preference order for documentation sources:

1. Official provider API docs
2. Official provider webhook/event docs
3. Official provider auth/OAuth docs
4. Official provider SDK docs
5. Official provider changelog
6. OpenAPI specification or public schema
7. Provider-maintained GitHub repositories

Third-party tutorials may be useful during implementation, but they should not be treated as canonical documentation.

## Documentation Index

### Source Control and Code Review

| Integration | API docs | Webhook/event docs | Auth/docs | Changelog/notes |
|---|---|---|---|---|
| GitHub | https://docs.github.com/en/rest | https://docs.github.com/en/webhooks | https://docs.github.com/en/apps/oauth-apps | https://docs.github.com/en/rest/overview/api-versions |
| GitLab | https://docs.gitlab.com/api/ | https://docs.gitlab.com/user/project/integrations/webhooks/ | https://docs.gitlab.com/api/oauth2/ | https://docs.gitlab.com/update/ |
| Bitbucket Cloud | https://developer.atlassian.com/cloud/bitbucket/rest/ | https://support.atlassian.com/bitbucket-cloud/docs/manage-webhooks/ | https://developer.atlassian.com/cloud/bitbucket/oauth-2/ | https://developer.atlassian.com/cloud/bitbucket/changelog/ |
| Azure DevOps | https://learn.microsoft.com/en-us/rest/api/azure/devops/ | https://learn.microsoft.com/en-us/azure/devops/service-hooks/overview | https://learn.microsoft.com/en-us/azure/devops/integrate/get-started/authentication/authentication-guidance | https://learn.microsoft.com/en-us/azure/devops/release-notes/ |

### Project and Issue Management

| Integration | API docs | Webhook/event docs | Auth/docs | Changelog/notes |
|---|---|---|---|---|
| Jira Cloud | https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/ | https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-webhooks/ | https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/ | https://developer.atlassian.com/cloud/jira/platform/changelog/ |
| Linear | https://linear.app/docs/api-and-webhooks | https://linear.app/developers/webhooks | https://linear.app/developers/oauth | https://linear.app/changelog |
| Azure Boards | https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/ | https://learn.microsoft.com/en-us/azure/devops/service-hooks/overview | https://learn.microsoft.com/en-us/azure/devops/integrate/get-started/authentication/authentication-guidance | https://learn.microsoft.com/en-us/azure/devops/release-notes/ |
| Asana | https://developers.asana.com/docs | https://developers.asana.com/docs/webhooks-guide | https://developers.asana.com/docs/oauth | https://developers.asana.com/docs/changelog |
| ClickUp | https://developer.clickup.com/reference | https://developer.clickup.com/docs/webhooks | https://developer.clickup.com/docs/authentication | https://developer.clickup.com/changelog |
| Trello | https://developer.atlassian.com/cloud/trello/rest/ | https://developer.atlassian.com/cloud/trello/guides/rest-api/webhooks/ | https://developer.atlassian.com/cloud/trello/guides/rest-api/authorization/ | https://developer.atlassian.com/cloud/trello/changelog/ |

### Documentation and Knowledge Systems

| Integration | API docs | Webhook/event docs | Auth/docs | Changelog/notes |
|---|---|---|---|---|
| Notion | https://developers.notion.com/reference/intro | https://developers.notion.com/reference/webhooks | https://developers.notion.com/docs/authorization | https://developers.notion.com/page/changelog |
| Confluence Cloud | https://developer.atlassian.com/cloud/confluence/rest/v1/intro/ | https://developer.atlassian.com/cloud/confluence/modules/webhook/ | https://developer.atlassian.com/cloud/confluence/oauth-2-3lo-apps/ | https://developer.atlassian.com/cloud/confluence/changelog/ |
| Google Drive | https://developers.google.com/drive/api/guides/about-sdk | https://developers.google.com/workspace/drive/api/guides/push | https://developers.google.com/identity/protocols/oauth2 | https://developers.google.com/workspace/drive/api/release-notes |
| Google Docs | https://developers.google.com/docs/api | Use Drive push notifications for file/resource changes | https://developers.google.com/identity/protocols/oauth2 | https://developers.google.com/docs/api/release-notes |
| Microsoft Graph / SharePoint / OneDrive | https://learn.microsoft.com/en-us/graph/api/overview | https://learn.microsoft.com/en-us/graph/change-notifications-overview | https://learn.microsoft.com/en-us/graph/auth/ | https://developer.microsoft.com/en-us/graph/changelog |
| Dropbox | https://www.dropbox.com/developers/documentation/http/documentation | https://www.dropbox.com/developers/reference/webhooks | https://www.dropbox.com/developers/reference/oauth-guide | https://www.dropbox.com/developers/documentation/http/documentation#changelog |

### Communication and Decision Capture

| Integration | API docs | Webhook/event docs | Auth/docs | Changelog/notes |
|---|---|---|---|---|
| Slack | https://docs.slack.dev/apis/web-api/ | https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks | https://docs.slack.dev/authentication/ | https://docs.slack.dev/changelog/ |
| Microsoft Teams / Graph | https://learn.microsoft.com/en-us/graph/teams-concept-overview | https://learn.microsoft.com/en-us/graph/change-notifications-overview | https://learn.microsoft.com/en-us/graph/auth/ | https://developer.microsoft.com/en-us/graph/changelog |
| Gmail | https://developers.google.com/workspace/gmail/api/guides | https://developers.google.com/workspace/gmail/api/guides/push | https://developers.google.com/identity/protocols/oauth2 | https://developers.google.com/workspace/gmail/api/release-notes |
| Outlook / Microsoft 365 Mail | https://learn.microsoft.com/en-us/graph/api/resources/mail-api-overview | https://learn.microsoft.com/en-us/graph/change-notifications-overview | https://learn.microsoft.com/en-us/graph/auth/ | https://developer.microsoft.com/en-us/graph/changelog |
| Discord | https://discord.com/developers/docs/intro | https://discord.com/developers/docs/resources/webhook | https://discord.com/developers/docs/topics/oauth2 | https://discord.com/developers/docs/change-log |

### Meetings and Transcripts

| Integration | API docs | Webhook/event docs | Auth/docs | Changelog/notes |
|---|---|---|---|---|
| Zoom | https://developers.zoom.us/docs/api/ | https://developers.zoom.us/docs/api/webhooks/ | https://developers.zoom.us/docs/integrations/oauth/ | https://developers.zoom.us/changelog/ |
| Google Calendar | https://developers.google.com/workspace/calendar/api/guides/overview | https://developers.google.com/workspace/calendar/api/guides/push | https://developers.google.com/identity/protocols/oauth2 | https://developers.google.com/workspace/calendar/api/release-notes |
| Microsoft Teams meetings | https://learn.microsoft.com/en-us/graph/cloud-communication-online-meeting-application-access-policy | https://learn.microsoft.com/en-us/graph/change-notifications-overview | https://learn.microsoft.com/en-us/graph/auth/ | https://developer.microsoft.com/en-us/graph/changelog |
| Otter.ai | https://otter.ai/help | Validate public API availability before implementation | Validate auth model before implementation | Candidate only |
| Fireflies.ai | https://docs.fireflies.ai/ | Validate webhook availability before implementation | https://docs.fireflies.ai/ | Candidate only |

### Security and Compliance Evidence

| Integration | API docs | Webhook/event docs | Auth/docs | Changelog/notes |
|---|---|---|---|---|
| SARIF 2.1.0 | https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html | File import only | Not applicable | https://github.com/oasis-tcs/sarif-spec |
| GitHub Code Scanning | https://docs.github.com/en/rest/code-scanning/code-scanning | GitHub webhook events and security alert events | https://docs.github.com/en/apps/oauth-apps | https://docs.github.com/en/rest/overview/api-versions |
| Semgrep | https://semgrep.dev/docs/semgrep-appsec-platform/semgrep-api | Validate Semgrep app/webhook capabilities per account tier | https://semgrep.dev/docs/semgrep-appsec-platform/semgrep-api | https://semgrep.dev/docs/release-notes |
| Snyk | https://docs.snyk.io/snyk-api | https://docs.snyk.io/developer-tools/snyk-api/using-specific-snyk-apis/webhooks-apis | https://docs.snyk.io/snyk-api/authentication-for-api | https://updates.snyk.io/ |
| OSV | https://google.github.io/osv.dev/api/ | No primary webhook requirement | Public API | https://osv.dev/list |
| Trivy | https://trivy.dev/latest/docs/ | File/CI output integration | Not applicable for file ingest | https://github.com/aquasecurity/trivy/releases |
| OWASP Dependency-Track | https://docs.dependencytrack.org/integrations/rest-api/ | https://docs.dependencytrack.org/integrations/notifications/ | https://docs.dependencytrack.org/integrations/rest-api/ | https://docs.dependencytrack.org/changelog/ |

### Observability and Incident Systems

| Integration | API docs | Webhook/event docs | Auth/docs | Changelog/notes |
|---|---|---|---|---|
| Sentry | https://docs.sentry.io/api/ | https://docs.sentry.io/integrations/integration-platform/webhooks/ | https://docs.sentry.io/api/auth/ | https://docs.sentry.io/product/changelog/ |
| Datadog | https://docs.datadoghq.com/api/latest/ | https://docs.datadoghq.com/integrations/webhooks/ | https://docs.datadoghq.com/account_management/api-app-keys/ | https://docs.datadoghq.com/release_notes/ |
| PagerDuty | https://developer.pagerduty.com/api-reference/ | https://developer.pagerduty.com/docs/webhooks-overview | https://developer.pagerduty.com/docs/authentication | https://developer.pagerduty.com/changelog/ |
| New Relic | https://docs.newrelic.com/docs/apis/intro-apis/introduction-new-relic-apis/ | https://docs.newrelic.com/docs/alerts/get-notified/notification-integrations/ | https://docs.newrelic.com/docs/apis/intro-apis/new-relic-api-keys/ | https://docs.newrelic.com/whats-new/ |
| Grafana | https://grafana.com/docs/grafana/latest/developers/http_api/ | https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/ | https://grafana.com/docs/grafana/latest/developers/http_api/auth/ | https://grafana.com/docs/grafana/latest/whatsnew/ |
| Prometheus Alertmanager | https://prometheus.io/docs/alerting/latest/alertmanager/ | https://prometheus.io/docs/alerting/latest/configuration/#webhook_config | Not applicable or deployment-specific | https://prometheus.io/docs/introduction/release-cycle/ |
| Opsgenie | https://docs.opsgenie.com/docs/api-overview | https://docs.opsgenie.com/docs/webhook-integration | https://docs.opsgenie.com/docs/api-key-management | https://docs.opsgenie.com/docs/release-notes |

### CRM, Customer Success, and Support

| Integration | API docs | Webhook/event docs | Auth/docs | Changelog/notes |
|---|---|---|---|---|
| Salesforce | https://developer.salesforce.com/docs/apis | https://developer.salesforce.com/docs/atlas.en-us.change_data_capture.meta/change_data_capture/cdc_intro.htm | https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_flows.htm | https://developer.salesforce.com/releases |
| HubSpot | https://developers.hubspot.com/docs/api/overview | https://developers.hubspot.com/docs/api/webhooks | https://developers.hubspot.com/docs/api/oauth-quickstart-guide | https://developers.hubspot.com/changelog |
| Zendesk | https://developer.zendesk.com/api-reference/ | https://developer.zendesk.com/documentation/webhooks/ | https://developer.zendesk.com/documentation/ticketing/using-the-zendesk-api/oauth-api-tutorial/ | https://developer.zendesk.com/changelog/ |
| Intercom | https://developers.intercom.com/docs/references/rest-api/api.intercom.io | https://developers.intercom.com/docs/build-an-integration/learn-more/webhooks | https://developers.intercom.com/docs/build-an-integration/learn-more/authentication | https://developers.intercom.com/docs/references/changelog |
| Help Scout | https://developer.helpscout.com/mailbox-api/ | https://developer.helpscout.com/webhooks/ | https://developer.helpscout.com/mailbox-api/overview/authentication/ | https://developer.helpscout.com/ |
| Gainsight | https://support.gainsight.com/gainsight_nxt/API_and_Developer_Docs | Validate current webhook/event model before implementation | Validate tenant auth model before implementation | Candidate only |
| ChurnZero | https://support.churnzero.com/hc/en-us/categories/360001141392-Integrations | Validate current API and webhook docs before implementation | Validate tenant auth model before implementation | Candidate only |

### MCP and Agent Ecosystem

| Integration | API/docs | Event/docs | Auth/docs | Changelog/notes |
|---|---|---|---|---|
| Model Context Protocol | https://modelcontextprotocol.io/docs/getting-started/intro | https://modelcontextprotocol.io/specification/ | https://modelcontextprotocol.io/specification/ | https://modelcontextprotocol.io/specification/ |
| MCP Registry | https://github.com/modelcontextprotocol/registry | Registry metadata and repo updates | GitHub/auth model depending on usage | https://github.com/modelcontextprotocol/registry/releases |
| GitHub MCP Server | https://github.com/github/github-mcp-server | MCP tool surface via server docs | GitHub token/OAuth model | https://github.com/github/github-mcp-server/releases |
| Filesystem MCP servers | Validate selected server docs | Local tool-call surface | Local policy model | Requires per-server review |
| Database MCP servers | Validate selected server docs | Tool-call surface | Database credentials | Requires per-server review |
| Browser automation MCP servers | Validate selected server docs | Tool-call surface | Browser/session credentials | Requires per-server review |

### Data and Analytics

| Integration | API docs | Webhook/event docs | Auth/docs | Changelog/notes |
|---|---|---|---|---|
| PostHog | https://posthog.com/docs/api | https://posthog.com/docs/webhooks | https://posthog.com/docs/api#authentication | https://posthog.com/changelog |
| GA4 | https://developers.google.com/analytics/devguides/reporting/data/v1 | Event export often via BigQuery, not webhooks | https://developers.google.com/identity/protocols/oauth2 | https://developers.google.com/analytics/devguides/releases |
| BigQuery | https://cloud.google.com/bigquery/docs/reference/rest | Eventing via Cloud services, not primary connector path | https://cloud.google.com/docs/authentication | https://cloud.google.com/bigquery/docs/release-notes |
| Snowflake | https://docs.snowflake.com/en/developer-guide/sql-api/index | Streams/tasks/event tables vary by use case | https://docs.snowflake.com/en/developer-guide/sql-api/authenticating | https://docs.snowflake.com/en/release-notes/overview |
| Supabase | https://supabase.com/docs/reference | https://supabase.com/docs/guides/database/webhooks | https://supabase.com/docs/guides/api/api-keys | https://supabase.com/changelog |
| Segment | https://segment.com/docs/api/ | https://segment.com/docs/connections/functions/ | https://segment.com/docs/api/ | https://segment.com/docs/release-notes/ |
| Mixpanel | https://developer.mixpanel.com/reference/overview | Validate webhook/export patterns per plan | https://developer.mixpanel.com/reference/authentication | https://developer.mixpanel.com/changelog |

## Maintenance Policy

Each integration entry should be refreshed at one of the following cadences.

| Risk level | Refresh cadence | Examples |
|---|---|---|
| High risk | Monthly | MCP servers, agent tools, CRM/support data, email, browser automation, database connectors |
| Medium risk | Quarterly | GitHub, Jira, Linear, Slack, Notion, Microsoft Graph, Google Workspace |
| Low risk | Semi-annually | SARIF, OSV, file-import formats, stable export schemas |

Each refresh should record:

- Date checked
- Docs URLs verified
- API version changed or unchanged
- Webhook payload changes
- Auth scope changes
- Rate limit changes
- Deprecation notices
- Required adapter changes

## Implementation Note

The docs index should eventually be machine-readable. A future `integration-docs.yml` can mirror this markdown file and support automated link checks, documentation freshness checks, and connector readiness dashboards.
