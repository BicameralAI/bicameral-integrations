# SPDX-License-Identifier: MIT
"""Behavior tests for the OSV connector and end-to-end normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.osv.connector import OsvConnector, parse_vuln

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "vulnerability.json"


def _vuln() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads():
    assert _vuln()["id"] == "OSV-2026-1234"


def test_parse_maps_summary_ref_url_metadata():
    obs = parse_vuln(_vuln())
    assert obs.excerpt.startswith("Incomplete URL host validation")
    assert obs.title == obs.excerpt
    assert obs.source_ref.source_id == "osv"
    assert obs.source_ref.ref == "OSV-2026-1234"
    assert obs.source_ref.url == "https://osv.dev/vulnerability/OSV-2026-1234"
    assert obs.timestamp == "2026-06-02T12:00:00Z"
    assert "example-pkg" in obs.metadata["packages"]
    assert "CVSS_V3" in obs.metadata["severity"]
    assert "CVE-2026-0001" in obs.metadata["aliases"]


def test_excerpt_falls_back_details_then_id():
    assert parse_vuln({"id": "OSV-X", "details": "boom"}).excerpt == "boom"
    assert parse_vuln({"id": "OSV-X"}).excerpt == "OSV-X"


def test_floors_excerpt_when_empty():
    obs = parse_vuln({})
    assert obs.excerpt == "osv-vuln" and obs.source_ref.ref == "osv-vuln"
    out = normalize([obs], adapter_version="osv/0.1.0")
    assert out[0].evidence[0].excerpt.strip()


def test_summary_details_redact_and_passed():
    # F1 (low): free-text summary/details are redact-and-passed (parity); the id floor is opaque.
    rec = {"id": "OSV-9", "summary": "reported by ana@corp.com", "details": "leaked AKIAIOSFODNN7EXAMPLE"}
    obs = parse_vuln(rec)
    assert "ana@corp.com" not in obs.title
    assert "AKIAIOSFODNN7EXAMPLE" not in obs.excerpt
    assert parse_vuln({"id": "OSV-9"}).source_ref.ref == "OSV-9"  # opaque id floor un-redacted


def test_optional_fields_wrong_type_or_empty_do_not_crash():
    # SG-2026-06-04-I: optional/wrong-typed schema must normalize, not crash.
    assert parse_vuln({"id": "A", "references": []}).source_ref.url == ""
    assert parse_vuln({"id": "A", "references": [{}]}).source_ref.url == ""
    assert parse_vuln({"id": "A", "references": ["x"]}).source_ref.url == ""
    assert parse_vuln({"id": "A", "severity": [{"type": "CVSS_V3"}]}).metadata["severity"] == "CVSS_V3:"
    assert parse_vuln({"id": "A", "severity": ["junk"]}).metadata["severity"] == ""
    assert parse_vuln({"id": "A", "aliases": [1, 2]}).metadata["aliases"] == "1,2"
    assert parse_vuln({"id": "A", "affected": ["junk"]}).metadata["packages"] == ""


def test_wrong_typed_leaves_do_not_crash():
    # Truthy non-string leaves / non-list containers must normalize, not crash.
    assert parse_vuln({"id": "A", "summary": 7}).excerpt == "A"  # non-str summary skipped
    assert parse_vuln({"id": "A", "references": {"a": 1}}).source_ref.url == ""  # dict, not list
    assert parse_vuln({"id": "A", "affected": [{"package": {"name": 123}}]}).metadata["packages"] == ""
    assert parse_vuln({"id": "A", "aliases": "CVE-1"}).metadata["aliases"] == ""  # str, not list
    assert parse_vuln({"id": "A", "severity": {"x": 1}}).metadata["severity"] == ""  # dict, not list
    out = normalize([parse_vuln({"id": "A", "summary": 7})], adapter_version="osv/0.1.0")
    assert out[0].evidence[0].excerpt.strip()


def test_end_to_end_normalizes():
    out = normalize(OsvConnector().observations(_vuln()), adapter_version="osv/0.1.0")
    assert len(out) == 1
    assert isinstance(out[0], AdapterEmission) and out[0].source_id == "osv"
