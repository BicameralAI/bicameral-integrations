"""GitHub pull-request connector: provider payloads into neutral Observations.

A GitHub ``pull_request`` webhook is an envelope — ``{action, number,
pull_request: {...}, repository}`` — where the PR number is at the top level and
the PR fields (``base``/``title``/``body``/``html_url``/``user``/``merged_at``)
are nested under ``pull_request``. ``parse_pull_request`` reads a flat PR object
(the shape the REST active-fetch path returns), so ``normalize_event`` rebuilds
that flat shape from the envelope (injecting the top-level ``number``) before
parsing. Webhook deliveries are signed ``X-Hub-Signature-256: sha256=<hex
HMAC-SHA256(secret, raw_body)>``; ``verify()`` strips the ``sha256=`` prefix and
reuses ``verify_hmac_hex`` (fail-closed, constant-time). The live REST fetch +
secret resolution stay in the operator runtime (see ``auth.md``).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from urllib.parse import urlsplit

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.webhook_security import (
    DeliveryDedupCache,
    WebhookVerificationError,
    header_value,
    verify_hmac_hex,
)


def parse_pull_request(payload: dict) -> Observation:
    """Map a GitHub pull-request object into a provider-neutral Observation.

    The excerpt is the PR body, falling back to the title when the body is
    empty. Provider-specific field knowledge stays here; normalization into an
    AdapterEmission is the universal adapter's job (ADR-0004).
    """
    repo = payload.get("base", {}).get("repo", {}).get("full_name", "")
    number = payload.get("number", "")
    title = payload.get("title", "")
    body = payload.get("body", "") or ""
    return Observation(
        source_ref=SourceRef(
            source_id="github",
            ref=f"{repo}#{number}",
            url=payload.get("html_url", ""),
            kind="pull_request",
        ),
        excerpt=body or title,
        mode=SourceMode.ACTIVE,
        title=title,
        author=payload.get("user", {}).get("login", ""),
        timestamp=payload.get("merged_at", ""),
    )


class GitHubConnector:
    """GitHub connector identity plus the shared PR-payload parse surface.

    Declares GitHub's supported modes. The live ``fetch_active`` HTTP path and
    webhook signature verification are deferred (no live API this cycle); this
    connector provides the provider-neutral parse surface both modes will share.
    """

    source_id = "github"
    capabilities = SourceCapabilities(
        modes=frozenset({SourceMode.ACTIVE, SourceMode.WEBHOOK})
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

    def can_handle_ref(self, ref: SourceRef) -> bool:
        if ref.source_id == "github":
            return True
        # Match on the URL host, not a substring: `"github.com" in url` would
        # also accept `https://github.com.evil.com` / `https://evil-github.com`
        # (CodeQL py/incomplete-url-substring-sanitization).
        host = (urlsplit(ref.url).hostname or "").lower()
        return host == "github.com" or host.endswith(".github.com")

    def observations(self, payload: dict) -> list[Observation]:
        return [parse_pull_request(payload)]

    def verify(self, *, headers: dict[str, str], body: bytes) -> bool:
        """X-Hub-Signature-256 ``sha256=`` hex HMAC over the raw body. Fail closed."""
        try:
            sig = header_value(headers, "X-Hub-Signature-256")
            if isinstance(sig, str) and sig.lower().startswith("sha256="):
                sig = sig[len("sha256="):]
            verify_hmac_hex(header_sig=sig, body=body, secret=self._secret)
            return True
        except (WebhookVerificationError, AttributeError, TypeError):
            return False

    def _delivery_id(self, headers: dict[str, str]) -> str:
        """Best-effort delivery id ('' when none) — GitHub's per-delivery GUID."""
        return header_value(headers, "X-GitHub-Delivery") or ""

    def normalize_event(self, *, headers: dict[str, str], body: bytes) -> list[Observation]:
        """Self-guard (re-verify), dedup, unwrap the PR envelope, parse. ``[]`` on reject."""
        if not self.verify(headers=headers, body=body):
            return []
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return []
        if not isinstance(payload, dict):
            return []
        if self._dedup is not None:
            delivery_id = self._delivery_id(headers)
            if delivery_id and self._dedup.is_duplicate("github", delivery_id):
                return []
            self._dedup.mark_seen("github", delivery_id)
        pull_request = payload.get("pull_request")
        if not isinstance(pull_request, dict):
            return []
        # Rebuild the flat PR object parse_pull_request expects: PR fields are
        # nested, but `number` lives at the envelope top level (inject it).
        pr = dict(pull_request)
        pr.setdefault("number", payload.get("number"))
        return [parse_pull_request(pr)]
