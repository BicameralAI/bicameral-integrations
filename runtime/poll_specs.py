# SPDX-License-Identifier: MIT
"""Per-connector poll specs for the live-poll client (ADR-0012).

Each ``build_<connector>_spec`` wires one ACTIVE/poll connector's `PollSpec`
(endpoint + auth + pagination + per-page item extractor) for `poll_client.poll`.
The secret is resolved by the connector's **``source_id``** (the `SecretResolver`
Protocol's `connector_id`); each connector's `auth.md` names the resolver key by
`source_id`. A blank secret raises a token-free `PollError` — fail-closed, no
request attempted.

Unverified wire details (envelope keys, pagination cursors, header versions) are
kept as **config** (callables / arguments) and carry inline "unverified" comments,
NOT asserted as fact — each is recorded in the connector's `auth.md` as the gate
before live-network wiring (verify-before-cite).
"""

from __future__ import annotations

import json

from .poll_auth import ApiKeyHeaderAuth, BasicAuth, BearerAuth, PollError
from .poll_client import OffsetPager, PageNumberPager, PageToken, PollSpec
from .secrets import SecretResolver


def _require_secret(resolver: SecretResolver, source_id: str) -> str:
    """Resolve a connector secret by ``source_id`` or fail closed (token-free)."""
    secret = resolver.resolve(source_id)
    if not secret:
        raise PollError(0, f"secret_unresolved:{source_id}")
    return secret


# --- anthropic_admin (usage; aggregate, PII-free) --------------------------------
# A1/A2 (UNVERIFIED): the top-level ``data`` envelope key and the page-token param
# name/transport are not in our verified contract (auth.md documents only
# "has_more + next_page"); both confirmed against live docs before real-network use.
_ANTHROPIC_BASE = "https://api.anthropic.com/v1/organizations/usage_report/messages"


def build_anthropic_admin_spec(
    resolver: SecretResolver,
    *,
    base_url: str = _ANTHROPIC_BASE,
    version: str = "2023-06-01",
    next_param: str = "page",  # A2 candidate — unverified
) -> PollSpec:
    """anthropic_admin: ``x-api-key`` + ``anthropic-version``; ``has_more``/``next_page`` cursor."""
    secret = _require_secret(resolver, "anthropic_admin")
    auth = ApiKeyHeaderAuth("x-api-key", secret, extra={"anthropic-version": version})
    return PollSpec(
        base_url=base_url,
        auth=auth,
        items=lambda page: page.get("data", []),  # A1 envelope assumption (config, not fact)
        pagination=PageToken(next_param=next_param),
    )


# --- openai_admin (audit logs; actor identity dropped by the connector) ----------
_OPENAI_BASE = "https://api.openai.com/v1/organization/audit_logs"


def build_openai_admin_spec(
    resolver: SecretResolver,
    *,
    base_url: str = _OPENAI_BASE,
    next_param: str = "after",  # unverified — OpenAI list convention; confirm for this endpoint
) -> PollSpec:
    """openai_admin: Bearer admin key; ``has_more``/``last_id`` cursor re-sent as ``after``."""
    secret = _require_secret(resolver, "openai_admin")
    return PollSpec(
        base_url=base_url,
        auth=BearerAuth(secret),
        items=lambda page: page.get("data", []),  # unverified envelope (OpenAI convention)
        # cursor: unverified (auth.md documents limit/after/before, not has_more/last_id)
        pagination=PageToken(next_param=next_param, token_field="last_id", has_more_field="has_more"),
    )


# --- devin (agentic sessions; free-text redacted by the connector) ---------------
def build_devin_spec(resolver: SecretResolver, *, base_url: str) -> PollSpec:
    """devin: Bearer ``cog_`` key. ``base_url`` is REQUIRED — the operator templates
    ``org_id`` into ``/v3/organizations/{org}/sessions`` (auth.md). Envelope key + cursor
    pagination verified against docs.devin.ai (2026-06-08)."""
    secret = _require_secret(resolver, "devin")
    return PollSpec(
        base_url=base_url,
        auth=BearerAuth(secret),
        items=lambda page: page.get("items", []),  # verified: list wraps under `items`
        # verified cursor: response end_cursor + has_next_page, re-sent as ?after=
        pagination=PageToken(next_param="after", token_field="end_cursor", has_more_field="has_next_page"),
    )


# --- copilot (aggregate metrics; PII-free; top-level JSON array) ------------------
_COPILOT_BASE = "https://api.github.com/orgs/ORG/copilot/metrics"  # operator sets {org}


def build_copilot_spec(
    resolver: SecretResolver,
    *,
    base_url: str = _COPILOT_BASE,
    api_version: str = "2022-11-28",  # valid (EOL 2028-03-10); latest is 2026-03-10
    per_page: int = 100,
) -> PollSpec:
    """copilot: Bearer (read:org); response is a top-level JSON array of day objects.

    Verified docs.github.com 2026-06-08: this endpoint paginates by `page`/`per_page`
    (max 100; the lookback is **100 days**, not 28). Page-number pagination stops on a
    short page. `per_page` must match what the operator's `base_url` sends (default 100
    = GitHub's default), so the short-page stop is accurate.
    """
    secret = _require_secret(resolver, "copilot")
    auth = BearerAuth(
        secret,
        extra={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": api_version},
    )
    return PollSpec(
        base_url=base_url,
        auth=auth,
        items=lambda page: page if isinstance(page, list) else [],  # top-level array
        pagination=PageNumberPager(page_param="page", per_page=per_page),
    )


# --- granola (meeting notes + transcript) ----------------------------------------
# verified against docs.granola.ai (2026-06-08): host public-api.granola.ai/v1,
# resource GET /notes with ?include=transcript; list envelope `notes`; cursor
# pagination (`cursor`/`hasMore`); incremental watermark is `created_after` (operator-side).
_GRANOLA_BASE = "https://public-api.granola.ai/v1/notes?include=transcript"


def build_granola_spec(resolver: SecretResolver, *, base_url: str = _GRANOLA_BASE) -> PollSpec:
    """granola: Bearer key. Notes (with embedded transcript) endpoint; the
    ``created_after`` watermark + two-phase commit stay operator-run."""
    secret = _require_secret(resolver, "granola")
    return PollSpec(
        base_url=base_url,
        auth=BearerAuth(secret),
        items=lambda page: page.get("notes", []),  # verified: list wraps under `notes`
        pagination=PageToken(next_param="cursor", token_field="cursor", has_more_field="hasMore"),
    )


# --- cursor (team daily-usage; PII-free allowlist; POST date-range body) ----------
# host `api.cursor.com` inferred — the path POST /teams/daily-usage-data is documented;
# confirm the host against live Cursor docs before real-network use (verify-before-cite).
_CURSOR_BASE = "https://api.cursor.com/teams/daily-usage-data"


def build_cursor_spec(
    resolver: SecretResolver, *, base_url: str = _CURSOR_BASE, body: dict | None = None
) -> PollSpec:
    """cursor: HTTP Basic (API key as username, empty password); POST a date-range body.

    The body field names/units are UNVERIFIED — the caller supplies the dict (e.g.
    ``{"startDate": …, "endDate": …}``); it is json-encoded, not baked. Envelope key
    ``data`` is also a config callable. No pagination (date-range bounded).
    """
    secret = _require_secret(resolver, "cursor")
    auth = BasicAuth(secret, "", extra={"Content-Type": "application/json"})
    return PollSpec(
        base_url=base_url,
        auth=auth,
        method="POST",
        body=json.dumps(body or {}).encode("utf-8"),  # caller-supplied date range (unverified shape)
        items=lambda page: page.get("data", []),  # unverified envelope (data? array?)
        pagination=None,
    )


# --- servicenow (ITSM incidents; redact-and-pass; offset pagination) --------------
def build_servicenow_spec(
    resolver: SecretResolver,
    *,
    instance: str,
    username: str,
    limit: int = 100,
    fields: str | None = None,
) -> PollSpec:
    """servicenow: HTTP Basic (integration ``username`` + resolved password); Table API
    incident poll with ``sysparm_offset`` pagination. ``instance``/``username`` are
    non-secret operator config; the password is resolved by ``source_id``. ``sysparm_limit``
    rides in ``base_url``; OffsetPager advances only ``sysparm_offset``."""
    password = _require_secret(resolver, "servicenow")
    base = f"https://{instance}/api/now/table/incident?sysparm_limit={limit}"
    if fields:
        base = _with_fields(base, fields)
    return PollSpec(
        base_url=base,
        auth=BasicAuth(username, password),
        items=lambda page: page.get("result", []),  # documented Table-API envelope
        pagination=OffsetPager(offset_param="sysparm_offset", limit=limit),
    )


def _with_fields(base: str, fields: str) -> str:
    """Append ``sysparm_fields`` to the base URL (string-built so no import churn)."""
    return f"{base}&sysparm_fields={fields}"
