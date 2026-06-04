# SPDX-License-Identifier: MIT
"""Behavior tests for the MCP Registry connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.mcp_registry.connector import McpRegistryConnector, parse_server

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "server.json"


def _entry() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads():
    assert _entry()["name"] == "io.example/postgres-mcp"


def test_parse_maps_title_and_description():
    obs = parse_server(_entry())
    assert obs.title == "Postgres MCP Server"
    assert obs.excerpt.startswith("Read-only Postgres inspection")


def test_parse_uses_repository_url_and_name_ref():
    obs = parse_server(_entry())
    assert obs.source_ref.source_id == "mcp_registry"
    assert obs.source_ref.ref == "io.example/postgres-mcp"
    assert obs.source_ref.url == "https://github.com/example/postgres-mcp"
    assert obs.metadata["version"] == "0.3.1"
    assert obs.metadata["repository_source"] == "github"


def test_excerpt_falls_back_to_title_then_name():
    entry = {"name": "io.x/bare", "repository": {}}
    obs = parse_server(entry)
    assert obs.excerpt == "io.x/bare"
    assert obs.source_ref.url == ""


def test_floors_excerpt_when_everything_empty():
    # No name/title/description and no repository → terminal literal keeps the
    # excerpt non-blank so the emission contract holds.
    obs = parse_server({})
    assert obs.excerpt == "mcp-server"
    out = normalize([obs], adapter_version="mcp_registry/0.1.0")
    assert out[0].evidence[0].excerpt.strip()


def test_end_to_end_normalizes():
    out = normalize(
        McpRegistryConnector().observations(_entry()),
        adapter_version="mcp_registry/0.1.0",
    )
    assert len(out) == 1
    assert isinstance(out[0], AdapterEmission) and out[0].source_id == "mcp_registry"
