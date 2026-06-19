"""Conformance tests: connector Observation -> SDK Evidence contract (GH #187, bicameral-sdk #7).

Golden mapping proven on recorded Observations (offline; a fixture pass earns Beta, not Live —
ADR-0012). Asserts the two load-bearing SDK invariants: status is always 'raw', and the capturer
is the connector (never a human actor).
"""

from __future__ import annotations

import pytest

from adapter.core.capabilities import SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.pipeline import normalize
from adapter.core.sdk_evidence import EvidenceExportError, to_sdk_evidence

_AKIA = "AKIAIOSFODNN7EXAMPLE"  # fake AWS key shape


def _obs(*, mode: SourceMode = SourceMode.WEBHOOK, excerpt: str = "a decision was made",
         author: str = "Jordan Park", timestamp: str = "2026-06-02T18:42:11Z") -> Observation:
    ref = SourceRef(source_id="linear", ref="PLAT-204", url="https://linear.app/x/PLAT-204", kind="issue")
    return Observation(source_ref=ref, excerpt=excerpt, mode=mode, title="t", author=author, timestamp=timestamp)


def test_maps_observation_to_sdk_evidence_shape():
    ev = to_sdk_evidence(_obs(), adapter_version="linear/0.1.0")
    assert ev["status"] == "raw"  # SDK invariant: evidence is never canonical
    assert ev["source"] == {
        "system": "linear", "resourceId": "PLAT-204",
        "resourceType": "issue", "url": "https://linear.app/x/PLAT-204",
    }
    assert ev["excerpt"]["excerpt"] == "a decision was made"
    assert ev["capturedAt"] == "2026-06-02T18:42:11Z"
    prov = ev["provenance"]
    assert prov["captureMethod"] == "webhook"
    assert prov["pipelineVersion"] == "linear/0.1.0"
    assert prov["sourceHash"].startswith("sha256:")
    assert ev["id"] == "PLAT-204"


def test_capture_method_follows_mode():
    assert to_sdk_evidence(_obs(mode=SourceMode.ACTIVE), adapter_version="v")["provenance"]["captureMethod"] == "active"
    assert to_sdk_evidence(_obs(mode=SourceMode.PASSIVE), adapter_version="v")["provenance"]["captureMethod"] == "passive"


def test_capturer_is_connector_never_the_human_actor():
    # The capturer is the connector (source id), NOT the observation's author — no human identity anywhere.
    ev = to_sdk_evidence(_obs(author="Jordan Park"), adapter_version="v")
    assert ev["provenance"]["capturedBy"] == {"actorId": "linear", "actorType": "connector"}
    blob = str(ev).lower()
    assert "jordan" not in blob and "park" not in blob


def test_captured_at_is_injectable():
    # The operator runtime may inject the true ingestion time; defaults to the observation timestamp.
    ev = to_sdk_evidence(_obs(timestamp="2026-01-01T00:00:00Z"), adapter_version="v",
                         captured_at="2026-06-18T05:00:00Z")
    assert ev["capturedAt"] == "2026-06-18T05:00:00Z"
    assert ev["provenance"]["capturedAt"] == "2026-06-18T05:00:00Z"


def test_secret_in_excerpt_is_screened():
    # FX-SEC-001 parity: a secret in the excerpt must never cross the export boundary.
    with pytest.raises(EvidenceExportError):
        to_sdk_evidence(_obs(excerpt=f"deploy key {_AKIA}"), adapter_version="v")


def test_normalize_emits_evidence_not_candidate():
    # SG-2026-06-18-D: a connector emits raw evidence, not a candidate decision.
    out = normalize([_obs()], adapter_version="linear/0.1.0")
    assert out[0].emission_type == "evidence"
