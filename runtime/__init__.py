"""Operator-runtime boundary layer (ADR-0012).

A thin, framework-free layer the operator's host (HTTP receiver / cron — not this
library) calls to drive a connector's ingest → verify → normalize → emit path.
"""

from .delivery import PollConnector, WebhookConnector, deliver_poll, deliver_webhook
from .gateway_mapping import emission_to_external_envelope
from .poll_auth import ApiKeyHeaderAuth, BasicAuth, BearerAuth, NoAuth, PollError
from .poll_client import (
    HttpTransport,
    OffsetPager,
    PageNumberPager,
    PageToken,
    PollSpec,
    UrllibTransport,
    poll,
)
from .poll_specs import (
    build_anthropic_admin_spec,
    build_copilot_spec,
    build_cursor_spec,
    build_devin_spec,
    build_granola_spec,
    build_mcp_registry_spec,
    build_openai_admin_spec,
    build_servicenow_spec,
)
from .google_oauth import OAuthRefreshError, RefreshTokenSecretResolver
from .local_config import (
    ConfigError,
    FileSecretResolver,
    LocalConfig,
    load_config,
    resolver_from,
)
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
    "emission_to_external_envelope",
    "SecretResolver",
    "MappingSecretResolver",
    "FileSecretResolver",
    "LocalConfig",
    "load_config",
    "resolver_from",
    "ConfigError",
    "RefreshTokenSecretResolver",
    "OAuthRefreshError",
    "poll",
    "PollError",
    "PollSpec",
    "PageToken",
    "OffsetPager",
    "PageNumberPager",
    "ApiKeyHeaderAuth",
    "BearerAuth",
    "BasicAuth",
    "NoAuth",
    "HttpTransport",
    "UrllibTransport",
    "build_anthropic_admin_spec",
    "build_openai_admin_spec",
    "build_devin_spec",
    "build_copilot_spec",
    "build_granola_spec",
    "build_cursor_spec",
    "build_servicenow_spec",
    "build_mcp_registry_spec",
]
