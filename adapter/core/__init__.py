"""Shared universal adapter contracts and data objects."""

from .capabilities import SourceCapabilities, SourceMode
from .contracts import (
    ActiveConnector,
    Connector,
    PollingConnector,
    WebhookConnector,
)
from .emissions import (
    AdapterEmission,
    AdvisoryResult,
    ConfidenceSurface,
    RoutingHint,
    SourceEvidence,
    SourceRef,
)
from .observations import Observation
from .pipeline import EmissionContractError, normalize, validate_emissions

__all__ = [
    "ActiveConnector",
    "AdapterEmission",
    "AdvisoryResult",
    "ConfidenceSurface",
    "Connector",
    "EmissionContractError",
    "Observation",
    "PollingConnector",
    "RoutingHint",
    "SourceCapabilities",
    "SourceEvidence",
    "SourceMode",
    "SourceRef",
    "WebhookConnector",
    "normalize",
    "validate_emissions",
]
