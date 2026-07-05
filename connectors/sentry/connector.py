# SPDX-License-Identifier: MIT
"""Sentry connector: issue webhook events into neutral Observations.

A Sentry issue webhook payload (the `installation`/issue-alert event wrapping
`data.issue`) maps to one provider-neutral Observation (trust tier T1, runtime
error/issue evidence). The live Events-API receipt and `Sentry-Hook-Signature`
verification reuse `adapter.core.webhook_security` (`Sentry-Hook-Signature` =
hex HMAC-SHA256 over the raw body); the live HTTP receipt + secret resolution
stay in the operator runtime (see ``auth.md``). Read-only evidence, no canonical
writes (ADR-0008).
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
    """A stripped string for str inputs, else '' (wire payloads carry any type)."""
    return value.strip() if isinstance(value, str) else ""


def parse_issue(event: dict) -> Observation:
    """Map a Sentry issue webhook event into a provider-neutral Observation.

    Unwraps the ``data.issue`` envelope when present; falls back to treating the
    payload as a bare issue object. Defends on absent/wrong-typed fields. The issue
    ``title`` (the exception message) and ``culprit`` (a code frame) are free text that
    routinely embeds connection strings / emails / tokens -> **redact-and-pass** (secret/
    PHI/PAN + email/phone scrubbed; FX-SEC-001 backstops only secret/PHI/PAN). The opaque
    ``shortId``/``id`` floor is NOT redacted. The full stack trace / event body is never read
    (data minimization).
    """
    data = event.get("data")
    issue = data.get("issue") if isinstance(data, dict) else None
    issue = issue if isinstance(issue, dict) else event
    iid = str(issue.get("id") or "sentry-issue")
    title = redact(_text(issue.get("title")))
    culprit = redact(_text(issue.get("culprit")))
    short = str(issue.get("shortId") or "")
    return Observation(
        source_ref=SourceRef(
            source_id="sentry", ref=iid, url=issue.get("permalink") or "", kind="issue"
        ),
        excerpt=title or culprit or short or iid,
        mode=SourceMode.WEBHOOK,
        title=title or short or iid,
        timestamp=str(issue.get("firstSeen") or ""),
        metadata={
            "action": event.get("action") or "",
            "level": issue.get("level") or "",
            "status": issue.get("status") or "",
            "short_id": short,
        },
    )


class SentryConnector:
    """Sentry connector identity, parse surface, and webhook verification.

    Trust tier T1. ``verify`` checks the ``Sentry-Hook-Signature`` (hex
    HMAC-SHA256 over the RAW body — not a re-serialized object) fail-closed;
    Sentry documents no replay-timestamp window, so dedup (best-effort, on a
    delivery id when one is present) is the only replay guard. The live HTTP
    receipt + secret/keyring resolution stay in the operator runtime.
    """

    source_id = "sentry"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.WEBHOOK}))

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
        """Hex HMAC-SHA256 over the raw body. Fail closed."""
        try:
            verify_hmac_hex(
                header_sig=header_value(headers, "Sentry-Hook-Signature"),
                body=body,
                secret=self._secret,
            )
            return True
        except (WebhookVerificationError, AttributeError, TypeError):
            return False

    def _delivery_id(self, headers: dict[str, str], payload: dict) -> str:
        """Best-effort delivery id for dedup ('' when none is derivable)."""
        rid = header_value(headers, "Request-ID")
        if rid:
            return rid
        data = payload.get("data")
        issue = data.get("issue") if isinstance(data, dict) else None
        issue = issue if isinstance(issue, dict) else payload
        return str(issue.get("id") or "")

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
        if not isinstance(payload, dict):  # valid JSON but not an object
            return []
        delivery_id = (
            self._delivery_id(headers, payload) or hashlib.sha256(body).hexdigest()
        )
        if self._dedup is not None:
            if self._dedup.is_duplicate("sentry", delivery_id):
                return []
            self._dedup.mark_seen("sentry", delivery_id)
        obs = parse_issue(payload)
        return [dataclasses.replace(obs, provider_event_id=delivery_id)]
