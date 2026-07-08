# SPDX-License-Identifier: MIT
"""Behavior tests for the atomic local-config writer (#227 LD7; FX-RUNTIME-004 write half).

Seed fail-closed (no example placeholder survives — audit #230 F3), atomicity + failure-path
hygiene (no secret-bearing temp litter, gitignore-matching temp name — audit #231 A1/F5), and
the write-side runtime-key allowlist.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from runtime.config_write import seeded_document, write_local_config
from runtime.local_config import ConfigError, load_config


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_seed_creates_loadable_config_with_empty_secrets(tmp_path):
    p = tmp_path / "bicameral.local.json"
    write_local_config(p, lambda doc: None)
    cfg = load_config(p)  # round-trips through the fail-closed loader
    for cid, block in cfg.connectors.items():
        for key, value in (block.get("secrets") or {}).items():
            assert value == "", f"seed left a placeholder value under {cid}.{key}"
    # fail-closed consequence: the emptied seed can never satisfy the credential gate
    assert all(v == "" for v in cfg.secret_map.values())


def test_seed_document_empties_only_secret_values():
    doc = seeded_document()
    linear = doc["connectors"]["linear"]
    assert linear["secrets"] == {"linear": "", "linear_webhook": ""}
    assert linear["runtime"] == {"page_size": 50}  # runtime defaults survive the seed


def test_write_preserves_unrelated_blocks_and_comments(tmp_path):
    p = tmp_path / "bicameral.local.json"
    original = {
        "_comment": "operator note",
        "connectors": {
            "linear": {"enabled": False, "secrets": {"linear": "keep-me"}, "runtime": {}},
            "zendesk": {"enabled": True, "secrets": {"zendesk": "z"}, "runtime": {}},
        },
        "mods": {"dependency_risk": {"enabled": True}},
        "gateway": {"endpoint": "", "token": ""},
    }
    p.write_text(json.dumps(original), encoding="utf-8")

    def mutate(doc: dict) -> None:
        doc["connectors"]["linear"]["secrets"]["linear"] = "lin_api_new"
        doc["connectors"]["linear"]["enabled"] = True

    write_local_config(p, mutate)
    after = _read(p)
    assert after["_comment"] == "operator note"
    assert after["connectors"]["zendesk"] == original["connectors"]["zendesk"]
    assert after["mods"] == original["mods"]
    assert after["connectors"]["linear"]["secrets"]["linear"] == "lin_api_new"


def test_undeclared_runtime_key_rejected(tmp_path):
    p = tmp_path / "bicameral.local.json"

    def mutate(doc: dict) -> None:
        doc["connectors"]["linear"]["runtime"]["endpoint"] = "https://evil.example"

    with pytest.raises(ConfigError) as exc:
        write_local_config(p, mutate)
    assert "runtime key(s) not declared" in str(exc.value)
    assert not p.exists()  # rejected write creates nothing


def test_success_leaves_no_temp_litter(tmp_path):
    p = tmp_path / "bicameral.local.json"
    write_local_config(p, lambda doc: None)
    assert [f.name for f in tmp_path.iterdir()] == ["bicameral.local.json"]


def test_failing_mutate_leaves_original_untouched_and_no_temp(tmp_path):
    p = tmp_path / "bicameral.local.json"
    write_local_config(p, lambda doc: None)
    before = p.read_bytes()

    def boom(doc: dict) -> None:
        raise ValueError("mutate failure")

    with pytest.raises(ValueError):
        write_local_config(p, boom)
    assert p.read_bytes() == before  # byte-identical
    assert [f.name for f in tmp_path.iterdir()] == ["bicameral.local.json"]  # no temp litter


def test_replace_failure_cleans_temp_named_inside_gitignore_glob(tmp_path, monkeypatch):
    # audit #231 A1: the temp name must match config/bicameral.local*.json so even a file that
    # somehow SURVIVES a crash is gitignored; the failure path must also remove it.
    p = tmp_path / "bicameral.local.json"
    seen: list[str] = []

    def failing_replace(src, dst):
        seen.append(Path(src).name)
        raise OSError("simulated crash at replace")

    monkeypatch.setattr("runtime.config_write.os.replace", failing_replace)
    with pytest.raises(OSError):
        write_local_config(p, lambda doc: None)
    assert seen and re.fullmatch(r"bicameral\.local\..+\.json", seen[0]), seen
    assert list(tmp_path.iterdir()) == []  # temp removed on the failure path
