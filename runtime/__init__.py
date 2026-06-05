"""Operator-runtime boundary layer (ADR-0012).

A thin, framework-free layer the operator's host (HTTP receiver / cron — not this
library) calls to drive a connector's ingest → verify → normalize → emit path.
"""

from .delivery import PollConnector, WebhookConnector, deliver_poll, deliver_webhook
from .gateway_mapping import emission_to_ingest_request
from .secrets import MappingSecretResolver, SecretResolver
from .sinks import (
    CollectingSink,
    EmissionSink,
    GatewayEmissionError,
    GatewayEmissionGated,
    GatewaySink,
)

__all__ = [
    "deliver_webhook",
    "deliver_poll",
    "WebhookConnector",
    "PollConnector",
    "EmissionSink",
    "CollectingSink",
    "GatewaySink",
    "GatewayEmissionGated",
    "GatewayEmissionError",
    "emission_to_ingest_request",
    "SecretResolver",
    "MappingSecretResolver",
]
