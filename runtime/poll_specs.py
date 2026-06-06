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

from .poll_client import (
    ApiKeyHeaderAuth,
    BearerAuth,
    PageToken,
    PollError,
    PollSpec,
)
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
    ``org_id`` into ``/v3/organizations/{org}/sessions`` (auth.md). Pagination is
    DEFERRED (the session-list cursor contract is unverified)."""
    secret = _require_secret(resolver, "devin")
    return PollSpec(
        base_url=base_url,
        auth=BearerAuth(secret),
        items=lambda page: page.get("sessions", []),  # unverified envelope (sessions? data?)
        pagination=None,  # cursor unverified — single page this cycle
    )


# --- copilot (aggregate metrics; PII-free; top-level JSON array) ------------------
_COPILOT_BASE = "https://api.github.com/orgs/ORG/copilot/metrics"  # operator sets {org}


def build_copilot_spec(
    resolver: SecretResolver,
    *,
    base_url: str = _COPILOT_BASE,
    api_version: str = "2022-11-28",  # unverified candidate — GitHub API version header
) -> PollSpec:
    """copilot: Bearer (read:org); response is a top-level JSON array of day objects."""
    secret = _require_secret(resolver, "copilot")
    auth = BearerAuth(
        secret,
        extra={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": api_version},
    )
    return PollSpec(
        base_url=base_url,
        auth=auth,
        items=lambda page: page if isinstance(page, list) else [],  # top-level array
        pagination=None,  # date-range bounded — one page
    )


# --- granola (meeting transcripts) -----------------------------------------------
_GRANOLA_BASE = "https://api.granola.ai/v1/transcripts"


def build_granola_spec(resolver: SecretResolver, *, base_url: str = _GRANOLA_BASE) -> PollSpec:
    """granola: Bearer key. The ``since`` watermark + two-phase commit stay operator-run;
    the harness supplies fetch only. Pagination DEFERRED (watermark is operator-side)."""
    secret = _require_secret(resolver, "granola")
    return PollSpec(
        base_url=base_url,
        auth=BearerAuth(secret),
        items=lambda page: page.get("transcripts", []),  # unverified envelope (transcripts? data?)
        pagination=None,
    )
