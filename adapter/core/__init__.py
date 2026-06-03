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
from .sensitive import SensitiveHit, detect_sensitive

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
    "SensitiveHit",
    "SourceCapabilities",
    "SourceEvidence",
    "SourceMode",
    "SourceRef",
    "WebhookConnector",
    "detect_sensitive",
    "normalize",
    "validate_emissions",
]
