# SPDX-License-Identifier: MIT
"""Delivery orchestration for the operator-runtime boundary (ADR-0012).

The operator's host (an HTTP receiver / cron — NOT this library) calls these to
drive a connector's ``ingest → verify → normalize → emit(sink)`` path. Webhook
connectors expose ``normalize_event`` (self-guarding verify + dedup); poll /
active connectors expose ``observations``. A blank or dropped result emits
nothing (returns 0). A true emission-contract breach (e.g. a sensitive-data hit)
propagates out of ``normalize`` to the operator — it is never silently swallowed.
"""

from __future__ import annotations

import logging
from typing import Protocol

from adapter.core.observations import Observation
from adapter.core.pipeline import normalize

from .sinks import EmissionSink
from .versioning import adapter_version_for

_MAX_BODY = 1_048_576  # 1 MiB — reject an oversized webhook body before parse/regex (#55)
_log = logging.getLogger(__name__)

# Data-shape confusion a malformed/hostile provider row can trigger inside a connector's
# parse (e.g. `(row.get(k) or "").strip()` on a non-string, `redact(non_str)`): skip that
# one row instead of aborting the whole batch (deep-audit Cycle 2). A genuine emission-
# contract breach is raised by `normalize`, NOT here, so it still propagates uncaught.
# OverflowError/OSError cover an out-of-range epoch int reaching time.gmtime/strftime
# (purple-team OPENAI-ADMIN-PARSE-1 / SG-2026-06-14-C) — a systemic per-row backstop.
_PARSE_SKIP = (AttributeError, TypeError, ValueError, LookupError, OverflowError, OSError)


class WebhookConnector(Protocol):
    """A connector with webhook verification wired."""

    source_id: str

    def normalize_event(
        self, *, headers: dict[str, str], body: bytes
    ) -> list[Observation]: ...


class PollConnector(Protocol):
    """A connector with a poll/active parse surface."""

    source_id: str

    def observations(self, payload: dict) -> list[Observation]: ...


def deliver_webhook(
    connector: WebhookConnector,
    *,
    headers: dict[str, str],
    body: bytes,
    sink: EmissionSink,
    adapter_version: str | None = None,
) -> int:
    """Verify+normalize a webhook delivery and emit; return the emission count.

    Returns 0 (and never calls ``sink.emit``) when the connector rejects or
    dedups the delivery, or when the body exceeds ``_MAX_BODY`` (#55). When
    ``adapter_version`` is None it derives ``<source_id>/<descriptor version>``
    from the connector descriptor (single source — see ``runtime.versioning``).
    """
    if len(body) > _MAX_BODY:  # bound parse/regex work on a hostile oversized payload
        return 0
    observations = connector.normalize_event(headers=headers, body=body)
    if not observations:
        return 0
    av = adapter_version or adapter_version_for(connector.source_id)
    emissions = normalize(observations, adapter_version=av)
    sink.emit(emissions)
    return len(emissions)


def deliver_poll(
    connector: PollConnector,
    payloads: list[dict],
    *,
    sink: EmissionSink,
    adapter_version: str | None = None,
) -> int:
    """Parse+normalize a batch of polled payloads and emit; return the count.

    When ``adapter_version`` is None it derives ``<source_id>/<descriptor version>``
    from the connector descriptor (single source — see ``runtime.versioning``).
    """
    observations: list[Observation] = []
    for payload in payloads:
        try:
            observations.extend(connector.observations(payload))
        except _PARSE_SKIP as exc:  # one bad row must not abort the batch (deep-audit Cycle 2)
            # Log the connector + exception type only — never the payload (PII/secret hygiene).
            _log.warning("deliver_poll: skipped a malformed %s row (%s)",
                         connector.source_id, type(exc).__name__)
            continue
    if not observations:
        return 0
    av = adapter_version or adapter_version_for(connector.source_id)
    emissions = normalize(observations, adapter_version=av)
    sink.emit(emissions)
    return len(emissions)
