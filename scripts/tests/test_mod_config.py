# SPDX-License-Identifier: MIT
"""Behavior tests for the mod descriptor contract (the EM-safe-mod parity of FX-CFG-001)."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_mod_index as bmi  # noqa: E402
import validate_mod_config as vmc  # noqa: E402

_REPO = Path(__file__).resolve().parents[2]
_MODS = _REPO / "mods"
_SCHEMA = json.loads((_MODS / "_schema" / "mod-descriptor.schema.json").read_text(encoding="utf-8"))


def _adapter_contract() -> dict:
    return json.loads((_MODS / "adapter_contract" / "config.json").read_text(encoding="utf-8"))


def test_all_mod_descriptors_valid_and_index_fresh():
    # Every committed mod descriptor conforms to the schema, agrees with its manifest, and the index is fresh.
    assert vmc.validate_all() == {}


def test_index_keys_match_descriptors():
    idx = bmi.build_index()["mods"]
    assert bmi.render(bmi.build_index()) == (_MODS / "index.json").read_text(encoding="utf-8")
    assert "adapter_contract" in idx and "noisy_source_gate" in idx


def test_descriptor_is_advisory_only_and_non_authoritative():
    d = _adapter_contract()
    assert d["ui"]["advisory_only"] is True
    assert d["em_safe"]["non_authoritative"] is True


def test_validator_rejects_emits_not_matching_manifest():
    # The UI 'emits' must equal the enforced manifest.yaml outputs — drift is fail-closed.
    d = copy.deepcopy(_adapter_contract())
    d["emits"] = d["emits"] + ["fabricated_output"]
    errs = vmc._semantic(d, "adapter_contract")
    assert any("emits" in e and "manifest" in e for e in errs)


def test_validator_rejects_forbidden_actions_not_matching_manifest():
    # The UI 'can never do' boundary must equal the enforced manifest — the UI can't under/over-state it.
    d = copy.deepcopy(_adapter_contract())
    d["em_safe"]["forbidden_actions"] = d["em_safe"]["forbidden_actions"][:-1]  # drop one
    errs = vmc._semantic(d, "adapter_contract")
    assert any("forbidden_actions" in e for e in errs)


def test_validator_rejects_id_folder_mismatch():
    d = copy.deepcopy(_adapter_contract())
    d["id"] = "not_the_folder"
    errs = vmc._semantic(d, "adapter_contract")
    assert any("!= folder" in e for e in errs)


def test_validator_rejects_unknown_key_fail_closed():
    d = copy.deepcopy(_adapter_contract())
    d["sneaky"] = True
    errs = vmc._check(d, _SCHEMA, "adapter_contract")  # the shared schema-subset checker
    assert any("unknown key" in e for e in errs)


def test_mod_version_and_channel_enforced():
    # Every mod carries a version (== manifest) + channel == product channel (uniform Beta state).
    import copy
    from product_meta import PRODUCT_CHANNEL
    d = _adapter_contract()
    assert d["version"] == "0.1.0" and d["channel"] == PRODUCT_CHANNEL
    bad = copy.deepcopy(d)
    bad["channel"] = "ga"
    assert any("channel" in e and "product channel" in e for e in vmc._semantic(bad, "adapter_contract"))
