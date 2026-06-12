# SPDX-License-Identifier: MIT
"""The emission adapter_version is single-sourced from the connector descriptor."""

from __future__ import annotations

import json
from pathlib import Path

from connectors.local_directory.connector import LocalDirectoryConnector
from runtime.delivery import deliver_poll
from runtime.sinks import EmissionSink
from runtime.versioning import adapter_version_for

_FIXTURE = Path(__file__).resolve().parents[2] / "connectors" / "local_directory" / "fixtures" / "note.json"


class _Capture(EmissionSink):
    def __init__(self) -> None:
        self.emissions: list = []

    def emit(self, emissions) -> None:
        self.emissions.extend(emissions)


def test_adapter_version_for_reads_descriptor_version():
    # Single source: <source_id>/<descriptor version> (local_directory descriptor version = 0.1.0).
    assert adapter_version_for("local_directory") == "local_directory/0.1.0"


def test_adapter_version_for_falls_back_for_unknown_source():
    # Fail-soft: a missing descriptor must not crash the emit path — fall back to the baseline.
    assert adapter_version_for("nonexistent_connector_xyz") == "nonexistent_connector_xyz/0.1.0"


def test_deliver_poll_stamps_per_connector_version_by_default():
    # With no explicit adapter_version, deliver_poll derives it from the connector descriptor
    # (so the emission a downstream gateway consumer sees carries the real per-connector version,
    # not the old generic "runtime/0.1.0").
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    sink = _Capture()
    deliver_poll(LocalDirectoryConnector(), [payload], sink=sink)
    assert sink.emissions and sink.emissions[0].adapter_version == "local_directory/0.1.0"


def test_explicit_adapter_version_still_honored():
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    sink = _Capture()
    deliver_poll(LocalDirectoryConnector(), [payload], sink=sink, adapter_version="custom/9.9.9")
    assert sink.emissions[0].adapter_version == "custom/9.9.9"
