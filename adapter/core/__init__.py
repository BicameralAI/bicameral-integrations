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
from .webhook_security import (
    DeliveryDedupCache,
    WebhookVerificationError,
    verify_hmac_hex,
    verify_standard_webhook,
)

__all__ = [
    "ActiveConnector",
    "AdapterEmission",
    "AdvisoryResult",
    "ConfidenceSurface",
    "Connector",
    "DeliveryDedupCache",
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
    "WebhookVerificationError",
    "detect_sensitive",
    "normalize",
    "validate_emissions",
    "verify_hmac_hex",
    "verify_standard_webhook",
]
