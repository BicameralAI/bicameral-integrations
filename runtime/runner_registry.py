# SPDX-License-Identifier: MIT
"""Connector + mod dispatch for the headless runner (ADR-0016 / FX-RUNTIME-004).

Maps a connector id to a uniform runner ``(resolver, runtime, document_id, transport, sink) -> int``,
absorbing the call-shape asymmetry (``poll`` takes a ``PollConnector`` first-arg; ``poll_graphql`` /
``fetch_document`` do not). Mod ids map to ``(mod, manifest_path)``. Data-driven so the connector
fan-out just adds a row. Stdlib-only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from connectors.anthropic_admin.connector import AnthropicAdminConnector
from connectors.copilot.connector import CopilotConnector
from connectors.cursor.connector import CursorConnector
from connectors.devin.connector import DevinConnector
from connectors.granola.connector import GranolaConnector
from connectors.mcp_registry.connector import McpRegistryConnector
from connectors.openai_admin.connector import OpenAIAdminConnector
from connectors.servicenow.connector import ServiceNowConnector
from mods.adapter_contract import AdapterContractMod
from mods.ai_authorship_review import AiAuthorshipReviewMod
from mods.authority_boundary import AuthorityBoundaryMod
from mods.code_review_risk import CodeReviewRiskMod
from mods.compliance_routing import ComplianceRoutingMod
from mods.connector_freshness import ConnectorFreshnessMod
from mods.contract import Manifest, Mod, load_manifest
from mods.cross_system_reference import CrossSystemReferenceMod
from mods.data_classification import DataClassificationMod
from mods.decision_drift import DecisionDriftMod
from mods.dependency_risk import DependencyRiskMod
from mods.noisy_source_gate import NoisySourceGateMod
from mods.notification_scope_risk import NotificationScopeRiskMod
from mods.ownership_routing import OwnershipRoutingMod
from mods.policy_exemption_audit import PolicyExemptionAuditMod
from mods.security_mentions import SecurityMentionsMod
from mods.source_trust_calibration import SourceTrustCalibrationMod
from mods.test_adequacy import TestAdequacyMod
from mods.webhook_risk import WebhookRiskMod

from .doc_fetch import fetch_document
from .graphql_poll import poll_graphql
from .local_config import ConfigError
from .poll_client import HttpTransport, poll
from .poll_specs import (
    build_anthropic_admin_spec,
    build_copilot_spec,
    build_cursor_spec,
    build_devin_spec,
    build_google_drive_spec,
    build_granola_spec,
    build_linear_graphql_spec,
    build_mcp_registry_spec,
    build_openai_admin_spec,
    build_servicenow_spec,
)
from .secrets import SecretResolver
from .sinks import EmissionSink

_MODS_DIR = Path(__file__).resolve().parents[1] / "mods"

Runner = Callable[[SecretResolver, dict, str, HttpTransport, EmissionSink], int]


def _run_linear(resolver, runtime, document_id, transport, sink) -> int:  # noqa: ARG001 (uniform shape)
    return poll_graphql(build_linear_graphql_spec(resolver, **runtime), transport, sink)


def _run_google_drive(resolver, runtime, document_id, transport, sink) -> int:
    doc_id = document_id or runtime.get("document_id", "")
    if not doc_id:
        raise ConfigError("google_drive: --document-id (or runtime.document_id) is required")
    return fetch_document(build_google_drive_spec(resolver, document_id=doc_id), transport, sink)


def _run_mcp_registry(resolver, runtime, document_id, transport, sink) -> int:  # noqa: ARG001
    """mcp_registry is PUBLIC (no auth) — its builder takes no resolver, so it needs a dedicated
    runner rather than `_rest_runner` (which passes the resolver positionally)."""
    return poll(McpRegistryConnector(), build_mcp_registry_spec(**runtime), transport=transport, sink=sink)


def _rest_runner(builder, connector_cls) -> Runner:
    """A REST poll runner: build the spec from `runtime` kwargs, then `poll(connector, spec, …)`."""
    def run(resolver, runtime, document_id, transport, sink) -> int:  # noqa: ARG001 (uniform shape)
        try:
            spec = builder(resolver, **runtime)
        except TypeError as exc:  # missing/extra runtime kwarg (e.g. devin needs base_url) — token-free
            raise ConfigError(f"bad/missing runtime config: {exc}") from None
        return poll(connector_cls(), spec, transport=transport, sink=sink)
    return run


RUNNERS: dict[str, Runner] = {
    "linear": _run_linear,
    "google_drive": _run_google_drive,
    "anthropic_admin": _rest_runner(build_anthropic_admin_spec, AnthropicAdminConnector),
    "openai_admin": _rest_runner(build_openai_admin_spec, OpenAIAdminConnector),
    "copilot": _rest_runner(build_copilot_spec, CopilotConnector),
    "granola": _rest_runner(build_granola_spec, GranolaConnector),
    "cursor": _rest_runner(build_cursor_spec, CursorConnector),
    "servicenow": _rest_runner(build_servicenow_spec, ServiceNowConnector),
    "devin": _rest_runner(build_devin_spec, DevinConnector),
    "mcp_registry": _run_mcp_registry,
}

_MODS: dict[str, tuple[Callable[[], Mod], Path]] = {
    "dependency_risk": (DependencyRiskMod, _MODS_DIR / "dependency_risk" / "manifest.yaml"),
    "data_classification": (DataClassificationMod, _MODS_DIR / "data_classification" / "manifest.yaml"),
    "noisy_source_gate": (NoisySourceGateMod, _MODS_DIR / "noisy_source_gate" / "manifest.yaml"),
    "security_mentions": (SecurityMentionsMod, _MODS_DIR / "security_mentions" / "manifest.yaml"),
    "adapter_contract": (AdapterContractMod, _MODS_DIR / "adapter_contract" / "manifest.yaml"),
    "source_trust_calibration": (SourceTrustCalibrationMod, _MODS_DIR / "source_trust_calibration" / "manifest.yaml"),
    "webhook_risk": (WebhookRiskMod, _MODS_DIR / "webhook_risk" / "manifest.yaml"),
    "connector_freshness": (ConnectorFreshnessMod, _MODS_DIR / "connector_freshness" / "manifest.yaml"),
    "code_review_risk": (CodeReviewRiskMod, _MODS_DIR / "code_review_risk" / "manifest.yaml"),
    "authority_boundary": (AuthorityBoundaryMod, _MODS_DIR / "authority_boundary" / "manifest.yaml"),
    "test_adequacy": (TestAdequacyMod, _MODS_DIR / "test_adequacy" / "manifest.yaml"),
    "ownership_routing": (OwnershipRoutingMod, _MODS_DIR / "ownership_routing" / "manifest.yaml"),
    "decision_drift": (DecisionDriftMod, _MODS_DIR / "decision_drift" / "manifest.yaml"),
    # Cycle 2 (brief #208 workstream e) — 5 new EM-safe advisory mods.
    "cross_system_reference": (CrossSystemReferenceMod, _MODS_DIR / "cross_system_reference" / "manifest.yaml"),
    "ai_authorship_review": (AiAuthorshipReviewMod, _MODS_DIR / "ai_authorship_review" / "manifest.yaml"),
    "policy_exemption_audit": (PolicyExemptionAuditMod, _MODS_DIR / "policy_exemption_audit" / "manifest.yaml"),
    "compliance_routing": (ComplianceRoutingMod, _MODS_DIR / "compliance_routing" / "manifest.yaml"),
    "notification_scope_risk": (NotificationScopeRiskMod, _MODS_DIR / "notification_scope_risk" / "manifest.yaml"),
}


def load_mod(mod_id: str) -> tuple[Mod, Manifest]:
    """Resolve a mod id to a (mod instance, Manifest). Fail-closed on unknown id / missing manifest."""
    entry = _MODS.get(mod_id)
    if entry is None:
        raise ConfigError(f"unknown mod: {mod_id!r}")
    cls, manifest_path = entry
    if not manifest_path.exists():
        raise ConfigError(f"{mod_id}: manifest not found at {manifest_path}")
    return cls(), load_manifest(manifest_path)
