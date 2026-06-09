# Research Brief — Google OAuth credentials for the google_drive live fetch

**Date**: 2026-06-08
**Analyst**: The Qor-logic Analyst
**Target**: Google OAuth 2.0 access/refresh tokens + service accounts, as the durable-credential path for
`google_drive` (`documents.get`); and whether a durable resolver can be **stdlib-only**.
**Scope**: token lifetime, refresh-token exchange mechanics, service-account JWT signing, scope
verification, and the drift between these and our shipped docs (the "blueprint").

> Governance note: this repo's governance is `scripts/governance_gate.py` + the hash-chained
> `docs/META_LEDGER.md` (NOT `qor-logic`/`ARCHITECTURE_PLAN.md`). The `qor-logic governance-health`
> preflight is recorded as a shortfall (tool not installed here); proceeding — research is non-severe.
> The "blueprint" cross-referenced is the **shipped** `connectors/google_drive/config.json` +
> `docs/CONNECTOR_BACKEND_SETUP.md` §5 claims.

---

## Executive Summary

Pasting a Google **access token** into the local config works but is a ~1-hour test only. The durable
in-repo path is a **refresh-token resolver**, which is **stdlib-feasible** — the refresh exchange is a
plain `urllib` form POST with **no RSA/JWT signing**. A **service-account** resolver is **NOT
stdlib-implementable**: it requires signing a JWT with **RS256 (RSA-SHA256)**, and the Python standard
library has no RSA signing. This is a hard finding that redirects the plan: build a stdlib
`RefreshTokenSecretResolver`; treat the service-account path as **operator-runtime** (needs `google-auth`)
and document it, do not claim a stdlib SA resolver. Our shipped docs DRIFT (imply a static stored token).

## Findings

### F1 — Access token lifetime: short-lived; honor `expires_in`
The token response carries `"expires_in"` (seconds) — Google's example shows `3920` (~65 min); the
documented default is ~1 hour. **A resolver MUST honor the returned `expires_in`** (cache until expiry,
re-fetch on expiry or a 401) rather than hardcoding a duration.
Source: developers.google.com/identity/protocols/oauth2/web-server (token response).

### F2 — Refresh-token exchange is a plain form POST, NO signing (stdlib-feasible)
- Endpoint: `https://oauth2.googleapis.com/token`; method **POST**; `Content-Type:
  application/x-www-form-urlencoded`.
- The token exchange "**No cryptographic signing is required**" (plain HTTPS form POST) — verified for the
  authorization-code grant on the same endpoint; the **refresh grant** uses the same endpoint with
  `grant_type=refresh_token` + `client_id` + `client_secret` + `refresh_token` → `{access_token,
  expires_in, scope, token_type}`.
- **Implication:** a `RefreshTokenSecretResolver` can be implemented with **stdlib `urllib`** (no RSA, no
  third-party dep) — consistent with the repo's stdlib-only invariant.
Source: developers.google.com/identity/protocols/oauth2/web-server (token exchange / refresh).

### F3 — Service account REQUIRES RS256 JWT signing (NOT stdlib)
- "The only signing algorithm supported by the Google OAuth 2.0 Authorization Server is **RSA using
  SHA-256** … expressed as `RS256`." The service account "Sign[s] … with the **private key**" from its
  JSON key.
- Token endpoint `https://oauth2.googleapis.com/token`, `grant_type=urn:ietf:params:oauth:grant-type:
  jwt-bearer`; JWT claims `iss` (SA email), `scope`, `aud`, `exp`, `iat`.
- **Implication (critical):** Python's standard library has **no RSA signing** (`hashlib` hashes but does
  not do RSA; there is no stdlib `rsa`/`cryptography`). So a service-account resolver **cannot be
  stdlib-only** — it needs `google-auth`/`cryptography` (third-party) or a subprocess to an external tool.
  This invalidates the previously-floated "stdlib ServiceAccountSecretResolver."
Source: developers.google.com/identity/protocols/oauth2/service-account.

### F4 — Service-account access to a Doc: share or delegate
A service account reads a Doc either (a) when the document is **shared with the SA's email**, or (b) via
**domain-wide delegation** (Workspace) to **impersonate** a specific user. (No interactive consent.)
Source: developers.google.com/identity/protocols/oauth2/service-account.

### F5 — Scope verification: only for distributed apps; testing needs none
- Drive/Docs scopes are **sensitive/restricted** (the exact list is in Google's OAuth verification FAQ,
  support.google.com/cloud/answer/9110914 — `documents.readonly`/`drive.readonly`/`drive.file` are the
  ones our connector uses).
- "Apps requesting sensitive or restricted … scopes to access **consumer data** require additional
  verification and potentially a security assessment." BUT "if your app is in the development, testing,
  or staging phases, **verification isn't required**" — a **Testing** app is "only available to users you
  add to the list of test users," subject to a tester warning, a **user cap**, and a **limited refresh-
  token lifetime** (Google's FAQ states 100 test users / 7-day refresh-token expiry in Testing).
- **Implication:** the operator's OWN account (Testing-mode OAuth client) or a **service account on own
  data** needs no verification — your "I'm not so sure Google would allow that" is correct **only** for a
  multi-tenant **published** app, not for own/internal use.
Source: developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification
+ the linked OAuth verification FAQ (support.google.com/cloud/answer/9110914).

### F6 — `documents.get` contract (re-confirmed)
`GET https://docs.googleapis.com/v1/documents/{documentId}`, `Authorization: Bearer <access_token>`;
scopes `documents.readonly`/`drive.readonly`/`drive.file`. (Matches FX-GDRIVE-002 / auth.md.)
Source: developers.google.com/docs/api/reference/rest/v1/documents/get (verified 2026-06-08, FX-GDRIVE-002).

## Blueprint Alignment

| Blueprint claim (shipped doc) | Actual finding | Status |
|---|---|---|
| `config.json` obtain.steps: "operator runtime **stores** the access token and OWNS refresh" | Access token is **short-lived (~1h)**; the durable credential is the **refresh token** (or SA JSON). "Stores the access token" implies a static API-key-like secret it is not. | **DRIFT** |
| `CONNECTOR_BACKEND_SETUP.md` §5: "return a valid access token (refresh it out-of-band)" | Honest on refresh but silent on: short lifetime, how to OBTAIN (OAuth client testing-mode / Playground / service account), and that a refresh resolver is stdlib-feasible while a SA resolver is not. | **DRIFT (incomplete)** |
| (Floated, not shipped) "build a stdlib ServiceAccountSecretResolver" | SA needs **RS256/RSA** → **not stdlib**. A **refresh-token** resolver IS stdlib (plain POST). | **DRIFT — redirect the build** |
| `BearerAuth(resolve("google_drive"))` → `Authorization: Bearer` | Correct — a valid access token works verbatim. | MATCH |

## Recommendations

1. **[L1 doc fix]** Correct `connectors/google_drive/config.json` obtain.steps + `CONNECTOR_BACKEND_SETUP.md`
   §5: access tokens are short-lived (honor `expires_in`); the durable credential is the **refresh token**
   (user OAuth) or **service-account JSON** (server); obtaining requires an OAuth client (**Testing mode =
   no verification** for own/test users) **or** the OAuth Playground (test) **or** a service account
   (server, no consent dance, share-the-doc / domain-wide delegation); restricted-scope **verification
   applies only to distributed/published apps on consumer data**. SETUP.md regenerates from the descriptor.
2. **[L2 build]** Add a **stdlib `RefreshTokenSecretResolver`** (FX-RUNTIME-006): given
   `refresh_token`+`client_id`+`client_secret` (gitignored/env), POST the refresh grant via `urllib`,
   return a fresh access token, **cache until `expires_in`** (re-fetch on expiry). No RSA → stdlib-only;
   token/secret never logged (GatewaySink discipline). Driven through the injected transport in tests
   (a mock does NOT promote to Live). This is the durable in-repo path matching "copy-paste a file."
3. **[Document, do NOT build stdlib]** The **service-account** path stays **operator-runtime** (needs
   `google-auth`/RS256). Document it (share-the-doc / domain-wide delegation) and that the operator's
   `SecretResolver` mints SA tokens — optionally a clearly-marked non-stdlib extra later; never claim a
   stdlib SA resolver.

## Updated Knowledge (lesson for the genome)

**Verify the crypto before promising stdlib.** A credential flow that "just needs a token" can hide an
RSA-signing requirement (service-account JWT = RS256) that the stdlib cannot satisfy — whereas the
superficially-similar refresh-token grant is a plain POST. Always check the *signing* requirement before
scoping an auth helper as stdlib-only. (Pairs with the verify-before-cite / "MEASURE the fix" doctrine.)

---

_Research complete. Findings are advisory — implementation decisions remain with the Governor._
