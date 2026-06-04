# SPDX-License-Identifier: MIT
"""Behavior tests for the SARIF connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.sarif.connector import SarifConnector, parse_result, parse_sarif

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "scan_report.json"


def _report() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads():
    assert "runs" in _report()


def test_parse_sarif_one_observation_per_result():
    obs = parse_sarif(_report())
    assert len(obs) == 2
    assert all(o.source_ref.source_id == "sarif" for o in obs)


def test_parse_result_maps_rule_and_message():
    result = _report()["runs"][0]["results"][0]
    obs = parse_result(result, "ExampleScanner")
    assert obs.title == "PY.no-eval"
    assert obs.excerpt == "Use of eval() on untrusted input."
    assert obs.metadata["level"] == "error"
    assert obs.metadata["uri"] == "src/handler.py"
    assert obs.metadata["start_line"] == "42"
    assert "src/handler.py" in obs.source_ref.ref


def test_parse_result_excerpt_falls_back_to_ruleid():
    result = {"ruleId": "PY.x", "message": {"text": ""}, "locations": []}
    obs = parse_result(result, "t")
    assert obs.excerpt == "PY.x"


def test_parse_result_floors_excerpt_when_empty():
    # No ruleId, no message, no location → terminal literal keeps excerpt
    # non-blank so the emission contract holds.
    obs = parse_result({}, "t")
    assert obs.excerpt == "sarif-result"
    out = normalize([obs], adapter_version="sarif/0.1.0")
    assert out[0].evidence[0].excerpt.strip()


def test_end_to_end_normalizes():
    out = normalize(
        SarifConnector().observations(_report()), adapter_version="sarif/0.1.0"
    )
    assert len(out) == 2
    assert all(isinstance(e, AdapterEmission) and e.source_id == "sarif" for e in out)
    assert out[0].evidence[0].excerpt.strip()
