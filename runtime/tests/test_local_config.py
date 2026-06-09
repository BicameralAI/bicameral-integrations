# SPDX-License-Identifier: MIT
"""Behavior tests for the operator-local config + resolver (FX-RUNTIME-004)."""

from __future__ import annotations

import json

import pytest

from runtime.local_config import (
    ConfigError,
    FileSecretResolver,
    assert_runnable,
    load_config,
)


def _write(tmp_path, obj) -> str:
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(obj), encoding="utf-8")
    return str(p)


def test_env_overrides_file(monkeypatch):
    r = FileSecretResolver({"linear": "file_val"})
    monkeypatch.setenv("BICAMERAL_LINEAR", "env_val")
    assert r.resolve("linear") == "env_val"          # set + non-empty wins
    monkeypatch.setenv("BICAMERAL_LINEAR", "")
    assert r.resolve("linear") == "file_val"          # set-but-empty falls through to file
    monkeypatch.delenv("BICAMERAL_LINEAR", raising=False)
    assert r.resolve("linear") == "file_val"          # absent -> file
    assert r.resolve("unknown_key") == ""             # unknown -> ""


def test_load_config_fail_closed(tmp_path):
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, ["not", "an", "object"]))
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, {"connectors": {}, "surprise": 1}))  # unknown top key
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, {"connectors": {"x": {"bogus": 1}}}))  # unknown connector key


def test_duplicate_credential_key_rejected(tmp_path):
    cfg = {"connectors": {
        "a": {"enabled": True, "secrets": {"shared": "1"}},
        "b": {"enabled": True, "secrets": {"shared": "2"}},
    }}
    with pytest.raises(ConfigError) as exc:
        load_config(_write(tmp_path, cfg))
    assert "duplicate credential key" in str(exc.value)


def test_load_config_builds_flat_secret_map(tmp_path):
    cfg = {"connectors": {"linear": {"enabled": True, "secrets": {"linear": "k", "linear_webhook": "w"}}}}
    config = load_config(_write(tmp_path, cfg))
    assert config.secret_map == {"linear": "k", "linear_webhook": "w"}


def test_assert_runnable_rejects_unknown_credential_key(tmp_path):
    # B3: a secret under an unknown credential key hard-fails, naming the KEY not the value.
    cfg = {"connectors": {"linear": {"enabled": True, "secrets": {"bogus": "SECRET_VALUE"}}}}
    config = load_config(_write(tmp_path, cfg))
    with pytest.raises(ConfigError) as exc:
        assert_runnable(config, "linear")
    assert "bogus" in str(exc.value)
    assert "SECRET_VALUE" not in str(exc.value)  # never leaks the value


def test_assert_runnable_rejects_missing_required(tmp_path, monkeypatch):
    monkeypatch.delenv("BICAMERAL_LINEAR", raising=False)
    monkeypatch.delenv("BICAMERAL_LINEAR_WEBHOOK", raising=False)
    cfg = {"connectors": {"linear": {"enabled": True, "secrets": {}}}}  # required creds absent
    config = load_config(_write(tmp_path, cfg))
    with pytest.raises(ConfigError) as exc:
        assert_runnable(config, "linear")
    assert "missing required" in str(exc.value)


# --- FX-RUNTIME-005: mode-scoped required credentials ---

import runtime.local_config as lc  # noqa: E402


def _cfg(connector_id: str, secrets: dict) -> lc.LocalConfig:
    return lc.LocalConfig(connectors={connector_id: {"enabled": True, "secrets": secrets}},
                          mods={}, gateway={}, secret_map=dict(secrets))


def test_assert_runnable_active_does_not_require_webhook_secret(monkeypatch):
    monkeypatch.delenv("BICAMERAL_LINEAR", raising=False)
    monkeypatch.delenv("BICAMERAL_LINEAR_WEBHOOK", raising=False)
    cfg = _cfg("linear", {"linear": "k"})  # only the active-mode key (real linear descriptor)
    lc.assert_runnable(cfg, "linear", mode="active")  # PASSES — webhook secret not required for active
    with pytest.raises(lc.ConfigError):
        lc.assert_runnable(cfg, "linear", mode="webhook")  # webhook mode STILL requires linear_webhook


def test_assert_runnable_empty_modes_treated_as_all_mode(monkeypatch):
    monkeypatch.setattr(lc, "_descriptor", lambda cid: {"credentials": [{"key": "x", "required": True, "modes": []}]})
    with pytest.raises(lc.ConfigError) as exc:  # B1: empty modes is all-mode, NOT never-required
        lc.assert_runnable(_cfg("c", {}), "c", mode="active")
    assert "missing required" in str(exc.value)


def test_assert_runnable_absent_modes_requires_all_modes(monkeypatch):
    monkeypatch.setattr(lc, "_descriptor", lambda cid: {"credentials": [{"key": "x", "required": True}]})  # no modes
    for mode in ("active", "webhook"):  # B2: backward-compat for the 24 future single-credential connectors
        with pytest.raises(lc.ConfigError):
            lc.assert_runnable(_cfg("c", {}), "c", mode=mode)


def test_unknown_key_rejected_any_mode(monkeypatch):
    monkeypatch.setattr(lc, "_descriptor", lambda cid: {"credentials": [{"key": "x", "required": True, "modes": ["active"]}]})
    for mode in ("active", "webhook"):  # A3: unknown-key check is mode-independent
        with pytest.raises(lc.ConfigError) as exc:
            lc.assert_runnable(_cfg("c", {"bogus": "v"}), "c", mode=mode)
        assert "unknown credential key" in str(exc.value)


def test_two_active_credentials_both_required(monkeypatch):
    monkeypatch.setattr(lc, "_descriptor", lambda cid: {"credentials": [
        {"key": "a", "required": True, "modes": ["active"]},
        {"key": "b", "required": True, "modes": ["active"]}]})
    with pytest.raises(lc.ConfigError) as exc:  # A4: relax only off-mode — both active creds required
        lc.assert_runnable(_cfg("c", {"a": "v"}), "c", mode="active")
    assert "b" in str(exc.value)
