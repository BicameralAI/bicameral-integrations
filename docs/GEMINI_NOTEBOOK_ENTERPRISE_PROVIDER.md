# Gemini Notebook Enterprise provider runtime boundary

Status: implementation guidance for the V1 external-reasoning provider governed by Bicameral Factory ADR-0004.

## Runtime composition

`runtime.notebooks.GeminiNotebookEnterpriseProvider` deliberately receives identity and credentials through operator-owned seams:

```python
from runtime.google_oauth import RefreshTokenSecretResolver
from runtime.notebooks import (
    GeminiNotebookEnterpriseProvider,
    GoogleUserInfoPrincipalResolver,
)

secrets = RefreshTokenSecretResolver(
    target_key="gemini_notebook_enterprise",
    refresh_token=refresh_token,
    client_id=client_id,
    client_secret=client_secret,
)

principal = GoogleUserInfoPrincipalResolver(
    secret_resolver=secrets,
    credential_key="gemini_notebook_enterprise",
)

provider = GeminiNotebookEnterpriseProvider(
    project_number=project_number,
    location="global",
    endpoint_location="global",
    secret_resolver=secrets,
    principal_resolver=principal,
)
```

This is composition guidance, not a new secret store. The refresh token, OAuth client id/secret, and access token remain operator-runtime material.

## OAuth consent requirements

The access token used for an identity-bound Notebook Enterprise V1 operation must be minted from a user grant that includes:

- `openid`
- `email`
- `https://www.googleapis.com/auth/discoveryengine.readwrite`

The first two scopes let `GoogleUserInfoPrincipalResolver` obtain the Google account subject and verified email from Google's OpenID Connect UserInfo endpoint. The Discovery Engine scope authorizes documented Notebook Enterprise REST operations.

If the notebook will ingest a Google Doc or Google Slides document by Drive id, the user grant also needs:

- `https://www.googleapis.com/auth/drive.readonly`

Google documents Drive-backed notebook sources as requiring Google **user** credentials. Do not substitute a service-account identity for the user-scoped POC and then treat API success as proof of the intended user's notebook.

### Existing Google Drive connector credential

The current `google_drive` connector consent descriptor grants `documents.readonly` and `drive.readonly`. That grant is appropriate for the connector's existing read path but is insufficient for the Notebook Enterprise provider because it lacks Notebook/Discovery Engine authorization and OIDC identity scopes.

Do not rename or silently widen the existing `google_drive` credential. Obtain a separate operator-side `gemini_notebook_enterprise` user grant with the required scopes, or explicitly re-consent a credential under an approved shared-credential design later.

## Principal verification

The caller supplies the intended `NotebookAccessScope.principal_ref`. Before notebook mutation:

1. `GoogleUserInfoPrincipalResolver` calls Google's documented OIDC UserInfo endpoint with the provider access token.
2. The resolver requires a non-empty Google `sub`, a non-empty email, and `email_verified=true`.
3. The provider compares that effective email to the requested principal case-insensitively.
4. A mismatch fails closed before the Notebook Enterprise mutation.

Google documents `sub`, not email, as the durable Google Account identifier. V1 uses verified email because the product acceptance boundary is an operator-visible Google Workspace identity. If Bicameral later persists a durable external principal record, preserve `sub` separately rather than treating email as immutable identity.

## Capability boundary

Gemini V1 advertises only `user` scope. `group` and `workspace` remain reserved contract values and fail closed before identity lookup or provider mutation.

Audio Overview is Preview / Pre-GA and defaults off. It is advertised only when the deployment explicitly enables the capability after provider/project validation.

## Evidence boundary

Safe receipts may include provider resource ids, project/location, effective verified principal, provider role/share facts, source ids and authoritative source references, operation status, and safe failure classes.

Never place OAuth tokens, refresh tokens, auth codes, client secrets, cookie/session material, raw UserInfo payloads, or routine raw source bodies into notebook receipts, MCP payloads, Product state, or logs.

## Terminal proof

Provider unit tests and a successful API call do not prove the product journey. Factory #497 remains the terminal witness: the exact created notebook must be visible/openable under the intended Bicameral Google Workspace user and reconcile with the sanitized provider evidence.
