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

from typing import Protocol

from adapter.core.observations import Observation
from adapter.core.pipeline import normalize

from .sinks import EmissionSink

_MAX_BODY = 1_048_576  # 1 MiB — reject an oversized webhook body before parse/regex (#55)


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
    adapter_version: str = "runtime/0.1.0",
) -> int:
    """Verify+normalize a webhook delivery and emit; return the emission count.

    Returns 0 (and never calls ``sink.emit``) when the connector rejects or
    dedups the delivery, or when the body exceeds ``_MAX_BODY`` (#55).
    """
    if len(body) > _MAX_BODY:  # bound parse/regex work on a hostile oversized payload
        return 0
    observations = connector.normalize_event(headers=headers, body=body)
    if not observations:
        return 0
    emissions = normalize(observations, adapter_version=adapter_version)
    sink.emit(emissions)
    return len(emissions)


def deliver_poll(
    connector: PollConnector,
    payloads: list[dict],
    *,
    sink: EmissionSink,
    adapter_version: str = "runtime/0.1.0",
) -> int:
    """Parse+normalize a batch of polled payloads and emit; return the count."""
    observations: list[Observation] = []
    for payload in payloads:
        observations.extend(connector.observations(payload))
    if not observations:
        return 0
    emissions = normalize(observations, adapter_version=adapter_version)
    sink.emit(emissions)
    return len(emissions)
