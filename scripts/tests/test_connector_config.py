# SPDX-License-Identifier: MIT
"""Behavior tests for the connector config descriptor contract (FX-CFG-001)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_connector_index as bci  # noqa: E402
import build_connector_setup as bcs  # noqa: E402
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


# --- backend setup docs (FX-CFG-001 grows) ---

import re  # noqa: E402


def _gdrive() -> dict:
    return json.loads((_CONNECTORS / "google_drive" / "config.json").read_text(encoding="utf-8"))


def test_setup_renders_from_descriptor():
    md = bcs.build_setup(_linear())
    assert "BICAMERAL_LINEAR" in md and "BICAMERAL_LINEAR_WEBHOOK" in md  # B1: per-credential env vars
    assert "webhook-*receive* path only" in md and "NOT** consumed by `runtime.cli run`" in md  # B2
    assert "python -m runtime.cli run linear" in md
    assert "you provision this inbound URL" in md  # receiver as instruction, not a value
    assert "## Go-live" in md


def test_setup_deterministic():
    d = _linear()
    assert bcs.build_setup(d) == bcs.build_setup(d)
    reordered = json.loads(json.dumps(d, sort_keys=True))  # B3: key-order-invariant
    assert bcs.build_setup(d) == bcs.build_setup(reordered)


def test_setup_generated_for_exemplars():
    for cid in ("linear", "google_drive"):
        md = (_CONNECTORS / cid / "SETUP.md").read_text(encoding="utf-8")
        assert md.startswith("<!-- GENERATED from config.json")
    gd = bcs.build_setup(_gdrive())
    assert "oauth2" in gd and "--document-id" in gd and "## Webhook setup" not in gd  # active-only


def test_setup_no_secret_shapes():
    # B4: the generated docs render placeholders only — no real secret shape.
    shapes = [r"lin_api_[A-Za-z0-9]{10,}", r"ya29\.[A-Za-z0-9_-]{10,}", r"\bAKIA[0-9A-Z]{16}\b",
              r"whsec_[A-Za-z0-9]{10,}", r"eyJ[A-Za-z0-9_-]+\.eyJ", r"Bearer [A-Za-z0-9._-]{12,}"]
    for path in _CONNECTORS.glob("*/SETUP.md"):
        text = path.read_text(encoding="utf-8")
        for shape in shapes:
            assert not re.search(shape, text), f"{path} matches {shape}"


def test_setup_docs_fresh():
    # B5: every SETUP.md is byte-fresh vs build_setup of its config.json (validate_all reports stale).
    assert vcc.validate_all() == {}  # exemplars fresh
    md_path = _CONNECTORS / "linear" / "SETUP.md"
    original = md_path.read_bytes()
    try:
        md_path.write_bytes(original + b"\ntampered\n")
        report = vcc.validate_all()
        assert any("SETUP.md" in k for k in report)
    finally:
        md_path.write_bytes(original)


def test_credential_modes_optional_and_validated():
    # FX-RUNTIME-005: credentials[].modes is enum-validated, optional; exemplars (with modes) stay fresh.
    assert vcc.validate_all() == {}
    d = _linear()
    del d["credentials"][0]["modes"]  # absent modes still structurally valid (all-mode at runtime)
    assert not [e for e in vcc._check(d, _SCHEMA, "x") if "modes" in e]
    d2 = _linear()
    d2["credentials"][0]["modes"] = ["bogus"]  # out-of-enum rejected
    assert any("not in" in e for e in vcc._check(d2, _SCHEMA, "x"))


def test_credential_modes_must_be_in_connector_modes():
    # FX-RUNTIME-005 defense-in-depth: a credential serving a mode the connector doesn't declare is rejected.
    d = _linear()  # connector modes ["webhook","active"]
    d["credentials"][0]["modes"] = ["passive"]  # not a Linear mode
    errs = vcc._semantic(d, "linear")
    assert any("not in connector modes" in e for e in errs)
