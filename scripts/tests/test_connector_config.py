# SPDX-License-Identifier: MIT
"""Behavior tests for the connector config descriptor contract (FX-CFG-001)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_connector_index as bci  # noqa: E402
import validate_connector_config as vcc  # noqa: E402

_REPO = Path(__file__).resolve().parents[2]
_CONNECTORS = _REPO / "connectors"
_SCHEMA = json.loads((_CONNECTORS / "_schema" / "connector-config.schema.json").read_text(encoding="utf-8"))


def _linear() -> dict:
    return json.loads((_CONNECTORS / "linear" / "config.json").read_text(encoding="utf-8"))


def test_exemplar_descriptors_valid():
    # Linear + Google Drive conform to the schema AND pass the code cross-check; index is fresh.
    assert vcc.validate_all() == {}


def test_index_is_fresh():
    committed = (_CONNECTORS / "index.json").read_text(encoding="utf-8")
    assert bci.render(bci.build_index()) == committed
    assert {"linear", "google_drive"} <= set(bci.build_index()["connectors"])


def test_linear_declares_two_credentials():
    d = _linear()
    types = {c["type"] for c in d["credentials"]}
    assert {"api_key", "webhook_secret"} <= types
    # the two-secret resolver gap is SURFACED, not hidden:
    assert any("two-secret" in g.lower() or "resolve" in g.lower() for g in d["wire_gates"])


def test_rejects_unknown_credential_type():
    d = _linear()
    d["credentials"][0]["type"] = "bogus"
    assert any("not in" in e for e in vcc._check(d, _SCHEMA, "x"))


def test_rejects_unknown_key_fail_closed():
    d = _linear()
    d["surprise"] = 1
    assert any("unknown key" in e for e in vcc._check(d, _SCHEMA, "x"))


def test_rejects_nested_unknown_key():
    # the hard guarantee: additionalProperties:false rejects unknown keys at NESTED objects too.
    d = _linear()
    d["webhook"]["receiver"]["surprise"] = 1
    d["credentials"][0]["obtain"]["surprise"] = 2
    errs = vcc._check(d, _SCHEMA, "x")
    assert sum("unknown key" in e for e in errs) >= 2


def test_rejects_wrong_scalar_type():
    # bool-not-string / string-not-bool must be caught (the schema leans on this for `available`/`required`).
    d = _linear()
    d["available"] = "yes"  # string where boolean required
    assert any("expected boolean" in e for e in vcc._check(d, _SCHEMA, "x"))


def test_rejects_out_of_enum_action():
    d = _linear()
    d["instructions"][0]["action"] = "frobnicate"
    assert any("not in" in e for e in vcc._check(d, _SCHEMA, "x"))


def test_rejects_id_not_matching_folder():
    d = _linear()
    d["id"] = "wrong"
    assert any("folder" in e for e in vcc._semantic(d, "linear"))


def test_rejects_missing_ref_on_open_url():
    d = _linear()
    d["instructions"] = [{"action": "open_url", "text": "go somewhere"}]  # no ref
    assert any("requires a 'ref'" in e for e in vcc._semantic(d, "linear"))


def test_modes_not_in_capabilities_rejected():
    # the real drift-guard: a synthetic descriptor with a mode NOT in LinearConnector's caps.
    # (the two exemplars can't trip this — Google Drive declares all 3 real modes.)
    d = _linear()
    d["modes"] = ["discovery"]  # DISCOVERY is a valid SourceMode but not in Linear's frozenset
    errs = vcc._semantic(d, "linear")
    assert any("not in capabilities" in e for e in errs)
