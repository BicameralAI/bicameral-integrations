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
    ProviderProvenance,
    RoutingHint,
    SourceEvidence,
    SourceRef,
)
from .observations import Observation
from .pipeline import EmissionContractError, normalize, validate_emissions
from .redaction import redact
from .sensitive import SensitiveHit, detect_sensitive, redact_catalog
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
    "ProviderProvenance",
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
    "redact",
    "redact_catalog",
    "validate_emissions",
    "verify_hmac_hex",
    "verify_standard_webhook",
]
