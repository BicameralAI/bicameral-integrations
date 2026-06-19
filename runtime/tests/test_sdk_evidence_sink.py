# SPDX-License-Identifier: MIT
"""Behavior tests for SdkEvidenceSink — to_sdk_evidence wired into the emit boundary (#212-A)."""

from __future__ import annotations

import pytest

from adapter.core.capabilities import SourceMode
from adapter.core.emissions import AdapterEmission, SourceEvidence, SourceRef
from adapter.core.observations import Observation
from adapter.core.pipeline import normalize
from adapter.core.sdk_evidence import EvidenceExportError, emission_to_sdk_evidence
from runtime.sinks import SdkEvidenceSink

_AKIA = "AKIAIOSFODNN7EXAMPLE"  # fake AWS key shape


def _emissions(excerpt: str = "a clean observation", author: str = "Jordan Park") -> list[AdapterEmission]:
    ref = SourceRef(source_id="linear", ref="PLAT-9", url="https://linear.app/x/PLAT-9", kind="issue")
    obs = Observation(source_ref=ref, excerpt=excerpt, mode=SourceMode.WEBHOOK,
                      title="t", author=author, timestamp="2026-06-02T00:00:00Z")
    return normalize([obs], adapter_version="linear/0.1.0")


def test_sink_emits_sdk_evidence_at_emit_boundary():
    sink = SdkEvidenceSink()  # default capture_method="active"
    sink.emit(_emissions())
    assert len(sink.evidence) == 1
    ev = sink.evidence[0]
    assert ev["status"] == "raw"
    assert ev["source"]["system"] == "linear"
    assert ev["provenance"]["captureMethod"] == "active"
    assert ev["provenance"]["pipelineVersion"] == "linear/0.1.0"
    assert ev["provenance"]["sourceHash"].startswith("sha256:")


def test_sink_capture_method_is_configurable():
    sink = SdkEvidenceSink(capture_method="webhook")
    sink.emit(_emissions())
    assert sink.evidence[0]["provenance"]["captureMethod"] == "webhook"


def test_sink_capturer_is_connector_never_human():
    sink = SdkEvidenceSink()
    sink.emit(_emissions(author="Jordan Park"))
    ev = sink.evidence[0]
    assert ev["provenance"]["capturedBy"] == {"actorId": "linear", "actorType": "connector"}
    assert "jordan" not in str(ev).lower()


def test_sink_accumulates_across_emits():
    sink = SdkEvidenceSink()
    sink.emit(_emissions("first"))
    sink.emit(_emissions("second"))
    assert [e["excerpt"]["excerpt"] for e in sink.evidence] == ["first", "second"]


def test_export_re_screens_secret_defensively():
    # A hand-built emission carrying a secret (bypassing normalize) is HARD-rejected by the export's
    # own FX-SEC-001 parity screen — the sink is a chokepoint independent of the upstream screen.
    ref = SourceRef(source_id="x", ref="r", url="", kind="k")
    ev = SourceEvidence(source_ref=ref, excerpt=f"deploy {_AKIA}", author="")
    poisoned = AdapterEmission(source_id="x", title="t", body="b", evidence=(ev,),
                               emission_type="evidence", adapter_version="x/1")
    with pytest.raises(EvidenceExportError):
        SdkEvidenceSink().emit([poisoned])


def test_emission_to_sdk_evidence_one_per_evidence_item():
    ref1 = SourceRef(source_id="s", ref="a", url="", kind="k")
    ref2 = SourceRef(source_id="s", ref="b", url="", kind="k")
    em = AdapterEmission(source_id="s", title="t", body="b",
                         evidence=(SourceEvidence(source_ref=ref1, excerpt="one"),
                                   SourceEvidence(source_ref=ref2, excerpt="two")),
                         emission_type="evidence", adapter_version="s/1")
    out = emission_to_sdk_evidence(em, capture_method="passive")
    assert [e["id"] for e in out] == ["a", "b"]
    assert all(e["provenance"]["captureMethod"] == "passive" for e in out)
