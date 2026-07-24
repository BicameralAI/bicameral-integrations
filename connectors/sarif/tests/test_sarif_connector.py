# SPDX-License-Identifier: MIT
"""Behavior tests for the SARIF connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission, SourceRef
from adapter.core.observations import Observation
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


def test_secret_in_message_is_scrubbed_and_finding_survives():
    # A secret-scanner finding whose message quotes the detected secret must be
    # scrubbed and emitted, not dropped. The security signal survives.
    result = {
        "ruleId": "secrets.hardcoded-aws-key",
        "message": {"text": "Detected AWS key AKIAIOSFODNN7EXAMPLE in config.py"},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": "config.py"},
                    "region": {"startLine": 3},
                }
            }
        ],
    }
    obs = parse_result(result, "gitleaks")
    assert "AKIAIOSFODNN7EXAMPLE" not in obs.excerpt
    assert "Detected AWS key" in obs.excerpt
    out = normalize([obs], adapter_version="sarif/0.1.0")
    assert out[0].evidence[0].excerpt.strip()
    assert "AKIAIOSFODNN7EXAMPLE" not in out[0].evidence[0].excerpt


def test_raw_secret_message_is_sanitized_by_universal_boundary():
    raw = Observation(
        source_ref=SourceRef(source_id="sarif", ref="x", kind="finding"),
        excerpt="Detected AWS key AKIAIOSFODNN7EXAMPLE in config.py",
    )
    emission = normalize([raw], adapter_version="sarif/0.1.0")[0]
    assert "AKIAIOSFODNN7EXAMPLE" not in emission.body
    assert emission.body == "Detected AWS key [redacted:secret] in config.py"
    assert emission.metadata["redaction_receipt"]["findings"] == [
        {"category": "secret", "action": "tokenized", "count": 1}
    ]


def test_non_catalog_token_in_message_now_scrubbed():
    # Tokens are assembled by concatenation so no literal shape appears in source.
    for token in (
        "xox" + "b-" + "123456789012-" + "a" * 16,
        "AIza" + "Sy" + "A" * 33,
        "sk" + "_live_" + "0" * 24,
    ):
        result = {
            "ruleId": "secrets.token",
            "message": {"text": f"Detected token {token} in app.py"},
            "locations": [
                {"physicalLocation": {"artifactLocation": {"uri": "app.py"}}}
            ],
        }
        obs = parse_result(result, "gitleaks")
        assert token not in obs.excerpt, token
        out = normalize([obs], adapter_version="sarif/0.1.0")
        assert token not in out[0].evidence[0].excerpt


def test_one_bad_result_does_not_drop_the_rest():
    report = {
        "runs": [
            {
                "tool": {"driver": {"name": "t"}},
                "results": [
                    {"ruleId": "ok", "message": {"text": "fine"}},
                    "not-a-dict",
                    7,
                ],
            }
        ]
    }
    obs = parse_sarif(report)
    assert len(obs) == 1 and obs[0].title == "ok"
    assert parse_sarif({"runs": {"x": 1}}) == []
    assert parse_sarif({"runs": [{"results": "nope"}]}) == []


def test_end_to_end_normalizes():
    out = normalize(
        SarifConnector().observations(_report()), adapter_version="sarif/0.1.0"
    )
    assert len(out) == 2
    assert all(isinstance(e, AdapterEmission) and e.source_id == "sarif" for e in out)
    assert out[0].evidence[0].excerpt.strip()
