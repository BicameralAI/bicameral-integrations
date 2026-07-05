# SPDX-License-Identifier: MIT
"""Jira Cloud connector: issue webhook events into neutral Observations.

A Jira Cloud issue webhook (`jira:issue_created` / `_updated` / `_deleted`) maps
to one provider-neutral Observation (trust tier T1). The human title is
``issue.fields.summary`` (a plain string); ``issue.fields.description`` is an
Atlassian Document Format (ADF) **object**, never a string, so the excerpt uses
``summary`` (never ADF). Classic webhooks with a configured secret sign delivery
``X-Hub-Signature: sha256=<hex-HMAC-SHA256(secret, raw_body)>`` (WebSub) —
``verify()`` strips the ``sha256=`` prefix and reuses
``adapter.core.webhook_security.verify_hmac_hex``, fail-closed + constant-time.
Jira documents no anti-replay window, so dedup (best-effort, on
``X-Atlassian-Webhook-Identifier`` then ``issue.id``) is the only replay guard.
The live HTTP receipt, REST fetch, secret resolution, and the Connect-JWT /
Forge / Automation auth paths are deferred (see ``auth.md``). Read-only evidence,
no canonical writes (ADR-0008); issue bodies carry PII/secrets, so the producer
sensitive screen (``FX-SEC-001``) is the guard.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from collections.abc import Callable

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.redaction import redact
from adapter.core.webhook_security import (
    DeliveryDedupCache,
    WebhookVerificationError,
    header_value,
    verify_hmac_hex,
)


def _text(value: object) -> str:
    """A stripped string for str inputs, else '' (ADF dicts / wrong types → '')."""
    return value.strip() if isinstance(value, str) else ""


def _nested(obj: dict, key: str, attr: str) -> str:
    """`obj[key][attr]` as text when both levels are dicts, else '' (SG-I)."""
    value = obj.get(key)
    return _text(value.get(attr)) if isinstance(value, dict) else ""


def parse_issue(event: dict) -> Observation:
    """Map a Jira issue webhook event into a provider-neutral Observation."""
    issue = event.get("issue")
    issue = issue if isinstance(issue, dict) else {}
    fields = issue.get("fields")
    fields = fields if isinstance(fields, dict) else {}
    key = _text(issue.get("key")) or _text(issue.get("id")) or "jira-issue"
    # summary is free-text -> redact-and-pass (never fields.description, an ADF object).
    summary = redact(_text(fields.get("summary")))
    return Observation(
        source_ref=SourceRef(
            source_id="jira",
            ref=key,
            url=_text(issue.get("self")),
            kind=_text(event.get("issue_event_type_name"))
            or _text(event.get("webhookEvent"))
            or "issue",
        ),
        excerpt=summary or key,
        mode=SourceMode.WEBHOOK,
        title=summary or key,
        author="",  # PII-safe: the actor's displayName (a real name) is NOT surfaced (SG-2026-06-11-D)
        timestamp=_text(fields.get("updated"))
        or _text(fields.get("created"))
        or str(event.get("timestamp") or ""),
        metadata={
            "event": _text(event.get("webhookEvent")),
            "status": _nested(fields, "status", "name"),
            "issuetype": _nested(fields, "issuetype", "name"),
            "project": _nested(fields, "project", "key"),
        },
    )


class JiraConnector:
    """Jira connector identity, parse surface, and webhook verification.

    Trust tier T1. ``verify`` checks the ``X-Hub-Signature`` (`sha256=` hex
    HMAC-SHA256 over the raw body) fail-closed; no anti-replay window (Jira
    documents none), so best-effort dedup is the replay guard. The live HTTP
    receipt + REST fetch + Connect-JWT/Forge/Automation auth are deferred.
    """

    source_id = "jira"
    capabilities = SourceCapabilities(
        modes=frozenset({SourceMode.WEBHOOK, SourceMode.ACTIVE})
    )

    def __init__(
        self,
        *,
        secret: str = "",
        dedup: DeliveryDedupCache | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        # Secret injected (keyring resolution stays in the operator runtime).
        self._secret = secret
        self._dedup = dedup
        self._clock = clock or time.time

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(
            payload, dict
        ):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_issue(payload)]

    def verify(self, *, headers: dict[str, str], body: bytes) -> bool:
        """X-Hub-Signature ``sha256=`` hex HMAC over the raw body. Fail closed."""
        try:
            sig = header_value(headers, "X-Hub-Signature")
            if isinstance(sig, str) and sig.lower().startswith("sha256="):
                sig = sig[len("sha256=") :]
            verify_hmac_hex(header_sig=sig, body=body, secret=self._secret)
            return True
        except (WebhookVerificationError, AttributeError, TypeError):
            return False

    def _delivery_id(self, headers: dict[str, str], payload: dict) -> str:
        """Best-effort delivery id ('' when none is derivable)."""
        ident = header_value(headers, "X-Atlassian-Webhook-Identifier")
        if ident:
            return ident
        issue = payload.get("issue")
        return str(issue.get("id") or "") if isinstance(issue, dict) else ""

    def normalize_event(
        self, *, headers: dict[str, str], body: bytes
    ) -> list[Observation]:
        """Self-guard (re-verify), best-effort dedup, then parse. ``[]`` on reject."""
        if not self.verify(headers=headers, body=body):
            return []
        try:
            payload = json.loads(body)
        except (
            ValueError,
            UnicodeDecodeError,
        ):  # ValueError covers JSONDecodeError + huge-int (#55)
            return []
        if not isinstance(payload, dict):
            return []
        delivery_id = (
            self._delivery_id(headers, payload) or hashlib.sha256(body).hexdigest()
        )
        if self._dedup is not None:
            if self._dedup.is_duplicate("jira", delivery_id):
                return []
            self._dedup.mark_seen("jira", delivery_id)
        obs = parse_issue(payload)
        return [dataclasses.replace(obs, provider_event_id=delivery_id)]
