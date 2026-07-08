# SPDX-License-Identifier: MIT
"""Behavior tests for the local-directory connector and normalization."""

from __future__ import annotations

import json
from pathlib import Path

from adapter.core.emissions import AdapterEmission
from adapter.core.pipeline import normalize
from connectors.local_directory.connector import (
    LocalDirectoryConnector,
    parse_file,
)

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "note.json"


def _payload() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_fixture_loads_as_dict():
    payload = _payload()
    assert isinstance(payload, dict)
    for key in ("path", "content", "modified"):
        assert key in payload


def test_parse_uses_content_as_excerpt():
    obs = parse_file(_payload())
    assert obs.excerpt == _payload()["content"]
    assert obs.source_ref.source_id == "local_directory"


def test_parse_derives_stem_title_and_token_ref():
    obs = parse_file(_payload())
    assert obs.title == "2026-06-01-event-store"
    assert obs.source_ref.ref.startswith("local-")
    # Deterministic: same path -> same token.
    assert parse_file(_payload()).source_ref.ref == obs.source_ref.ref


def test_parse_falls_back_to_stem_when_content_empty():
    payload = _payload()
    payload["content"] = ""
    obs = parse_file(payload)
    assert obs.excerpt == "2026-06-01-event-store"


def test_content_redact_and_pass_scrubs_email_and_phone():
    # F1 (medium): operator-dropped file content is redact-and-passed — email/phone scrubbed.
    payload = _payload()
    payload["content"] = "Reach Dana at dana@corp.com or +1 415 555 0199 about the rollout."
    obs = parse_file(payload)
    assert "dana@corp.com" not in obs.excerpt
    assert "555 0199" not in obs.excerpt
    assert "rollout" in obs.excerpt  # non-sensitive evidence text preserved


def test_filename_stem_redact_and_passes_email():
    # F2 (low): a PII-bearing filename (email in the stem) is scrubbed from title + excerpt floor.
    payload = _payload()
    payload["path"] = "inbox/contact-jane@corp.com-notes.md"
    payload["content"] = ""
    obs = parse_file(payload)
    assert "jane@corp.com" not in obs.title
    assert "jane@corp.com" not in obs.excerpt


def test_source_type_label_redact_and_passes():
    # purple-team #170 (ld-1): a freeform operator source_type_label is redact-and-passed into kind.
    payload = _payload()
    payload["source_type_label"] = "ping ops@corp.com"
    obs = parse_file(payload)
    assert "ops@corp.com" not in obs.source_ref.kind
    # a clean label survives unchanged
    payload["source_type_label"] = "incident-notes"
    assert parse_file(payload).source_ref.kind == "incident-notes"


def test_path_token_ref_is_opaque_not_redacted():
    # The sha256 path token is an opaque floor — stable, and never the filesystem layout.
    payload = _payload()
    payload["path"] = "secret/dir/+1-415-555-0199.md"
    obs = parse_file(payload)
    assert obs.source_ref.ref.startswith("local-")
    assert "415" not in obs.source_ref.ref  # hashed, not the raw path
    assert "/" not in obs.source_ref.ref


def test_end_to_end_normalizes_to_emission():
    payload = _payload()
    out = normalize(
        LocalDirectoryConnector().observations(payload),
        adapter_version="local_directory/0.1.0",
    )
    assert len(out) == 1
    assert isinstance(out[0], AdapterEmission)
    assert out[0].source_id == "local_directory"
    assert out[0].evidence[0].excerpt == payload["content"]
