# SPDX-License-Identifier: MIT
"""GitLab connector: merge-request / issue webhook events into neutral Observations.

A GitLab webhook delivers an envelope whose event kind is named by ``object_kind``
(``"merge_request"`` / ``"issue"``); the event fields live under
``object_attributes`` (``iid``, ``title``, ``description``, ``url``, ``action``) and
``project.path_with_namespace`` identifies the project. ``observations`` dispatches
on ``object_kind`` to the matching parse function (unknown kinds yield ``[]``).

Unlike GitHub, GitLab does NOT HMAC-sign the body: it sends the configured secret
verbatim in the ``X-Gitlab-Token`` header. ``verify()`` therefore delegates to
``verify_shared_token`` (constant-time plaintext equality, fail-closed). The newer
Standard-Webhooks *signing token* path (same Svix scheme ``connectors/fathom`` uses)
is a documented future enhancement (see ``auth.md``), not wired here. The live REST
fetch + token resolution stay in the operator runtime.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from urllib.parse import urlsplit

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.redaction import redact
from adapter.core.webhook_security import (
    DeliveryDedupCache,
    WebhookVerificationError,
    header_value,
    verify_shared_token,
)


def _event_observation(payload: dict, *, kind: str, sep: str) -> Observation:
    """Map a GitLab ``object_attributes`` event body into an Observation.

    Shared by the merge-request and issue surfaces (they differ only in the ref
    separator and kind). MR/issue ``title`` + ``description`` are free text ->
    **redact-and-pass** (secret/PHI/PAN + email/phone scrubbed; the github standard, since
    FX-SEC-001 backstops only secret/PHI/PAN). ``author`` is the PUBLIC GitLab ``username``
    (the artifact author, the kept-public-login precedent github set; reads only ``username``,
    not name/email) and is NOT redacted. Blank title/description floor to a non-blank literal so
    the emission contract's non-blank-excerpt rule is satisfied.
    """
    floor = f"gitlab-{kind.replace('_', '-')}"
    # isinstance-guard each nested container: `or {}` floors only FALSY — a truthy non-dict
    # (provider drift / hostile signed body) would crash `.get()` (purple-team GITLAB-001; the
    # fathom #164 class, jira's pattern).
    attrs = payload.get("object_attributes")
    attrs = attrs if isinstance(attrs, dict) else {}
    project_obj = payload.get("project")
    project = (
        (project_obj.get("path_with_namespace", "") or "")
        if isinstance(project_obj, dict)
        else ""
    )
    user_obj = payload.get("user")
    username = (
        (user_obj.get("username", "") or "") if isinstance(user_obj, dict) else ""
    )
    ref = f"{project}{sep}{attrs.get('iid', '')}".strip()
    title = redact((attrs.get("title") or "").strip())
    body = (attrs.get("description") or "").strip()
    return Observation(
        source_ref=SourceRef(
            source_id="gitlab",
            ref=ref if ref not in ("", sep) else floor,
            url=attrs.get("url", "") or "",
            kind=kind,
        ),
        excerpt=redact(body) or title or floor,
        mode=SourceMode.WEBHOOK,
        title=title or floor,
        author=username,
    )


def parse_merge_request(payload: dict) -> Observation:
    """Map a GitLab ``merge_request`` webhook event into an Observation (ref uses ``!iid``)."""
    return _event_observation(payload, kind="merge_request", sep="!")


def parse_issue(payload: dict) -> Observation:
    """Map a GitLab ``issue`` webhook event into an Observation (ref uses ``#iid``)."""
    return _event_observation(payload, kind="issue", sep="#")


class GitLabConnector:
    """GitLab connector identity plus the merge-request / issue parse surface.

    Declares GitLab's supported modes. Verification is a constant-time plaintext
    ``X-Gitlab-Token`` comparison (fail-closed); the live REST ``fetch_active``
    path and token resolution are deferred to the operator runtime (``auth.md``).
    """

    source_id = "gitlab"
    capabilities = SourceCapabilities(
        modes=frozenset({SourceMode.WEBHOOK, SourceMode.ACTIVE})
    )
    _PARSERS = {"merge_request": parse_merge_request, "issue": parse_issue}

    def __init__(
        self,
        *,
        secret: str = "",
        dedup: DeliveryDedupCache | None = None,
    ) -> None:
        # Secret injected (keyring resolution stays in the operator runtime).
        self._secret = secret
        self._dedup = dedup

    def can_handle_ref(self, ref: SourceRef) -> bool:
        if ref.source_id == "gitlab":
            return True
        # Match on URL host, not a substring (py/incomplete-url-substring-sanitization).
        host = (urlsplit(ref.url).hostname or "").lower()
        return host == "gitlab.com" or host.endswith(".gitlab.com")

    def observations(self, payload: dict) -> list[Observation]:
        """Dispatch on ``object_kind``; unknown / missing kinds yield ``[]``."""
        if not isinstance(
            payload, dict
        ):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        parser = self._PARSERS.get(payload.get("object_kind", ""))
        return [parser(payload)] if parser else []

    def verify(self, *, headers: dict[str, str], body: bytes) -> bool:
        """Constant-time ``X-Gitlab-Token`` plaintext-token equality. Fail closed."""
        try:
            verify_shared_token(
                header_token=header_value(headers, "X-Gitlab-Token"),
                secret=self._secret,
            )
            return True
        except (WebhookVerificationError, AttributeError, TypeError):
            return False

    def _delivery_id(self, headers: dict[str, str]) -> str:
        """Best-effort delivery id ('' when none) — GitLab's per-event UUID."""
        return header_value(headers, "X-Gitlab-Event-UUID") or ""

    def normalize_event(
        self, *, headers: dict[str, str], body: bytes
    ) -> list[Observation]:
        """Self-guard (re-verify), dedup, then dispatch on ``object_kind``. ``[]`` on reject."""
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
        delivery_id = self._delivery_id(headers) or hashlib.sha256(body).hexdigest()
        if self._dedup is not None:
            if self._dedup.is_duplicate("gitlab", delivery_id):
                return []
            self._dedup.mark_seen("gitlab", delivery_id)
        return [
            dataclasses.replace(o, provider_event_id=delivery_id)
            for o in self.observations(payload)
        ]
