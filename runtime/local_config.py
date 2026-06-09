# SPDX-License-Identifier: MIT
"""Operator-local config + secret resolution for the headless runner (ADR-0016).

Lets an operator drive connectors + mods WITHOUT the mcp UI: a gitignored
``config/bicameral.local.json`` (secrets + runtime + which connectors/mods are enabled), with
env vars (``BICAMERAL_<KEY>``) overriding so prod/CI need no file on disk. Secrets stay off the
wire here — this only RESOLVES them for the runtime; ``FileSecretResolver`` never logs/echoes a value.
The descriptors (``connectors/<id>/config.json``) declare *what* is needed; this supplies the values
and cross-checks the two. Stdlib-only.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = _REPO / "config" / "bicameral.local.json"
_CONNECTORS_DIR = _REPO / "connectors"
_ENV_PREFIX = "BICAMERAL_"
_TOP_KEYS = frozenset({"connectors", "mods", "gateway"})
_CONNECTOR_KEYS = frozenset({"enabled", "secrets", "runtime"})


class ConfigError(ValueError):
    """Raised when the local config is malformed or a run target is mis-credentialed (token-free)."""


@dataclass(frozen=True)
class LocalConfig:
    """Parsed operator config. ``secret_map`` is the flat {credential_key: value} across connectors."""

    connectors: dict
    mods: dict
    gateway: dict
    secret_map: dict


class FileSecretResolver:
    """``SecretResolver`` over env then the flat file map. ``BICAMERAL_<KEY>`` wins only when set AND
    non-empty (a set-but-empty env var falls through to the file). Never logs/echoes a secret."""

    def __init__(self, secret_map: dict) -> None:
        self._map = dict(secret_map)

    def resolve(self, connector_id: str) -> str:
        env = os.environ.get(_ENV_PREFIX + connector_id.upper())
        if env:  # set and non-empty
            return env
        return self._map.get(connector_id, "")


def load_config(path: str | Path = DEFAULT_CONFIG) -> LocalConfig:
    """Read + fail-closed-validate the local config; build the flat secret map (dup-key rejected)."""
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"config not found: {p} (copy config/bicameral.example.json)")
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigError("config root must be an object")
    unknown = {k for k in raw if not k.startswith("_")} - _TOP_KEYS  # _-prefixed keys are comments
    if unknown:
        raise ConfigError(f"unknown top-level keys: {sorted(unknown)}")
    connectors = raw.get("connectors") or {}
    secret_map: dict[str, str] = {}
    for cid, block in connectors.items():
        if cid.startswith("_"):  # comment row
            continue
        if not isinstance(block, dict):
            raise ConfigError(f"connector {cid!r} must be an object")
        bad = {k for k in block if not k.startswith("_")} - _CONNECTOR_KEYS
        if bad:
            raise ConfigError(f"connector {cid!r} unknown keys: {sorted(bad)}")
        for key in (block.get("secrets") or {}):
            if key in secret_map:
                raise ConfigError(f"duplicate credential key across connectors: {key!r}")
            secret_map[key] = block["secrets"][key]
    return LocalConfig(connectors, raw.get("mods") or {}, raw.get("gateway") or {}, secret_map)


def resolver_from(config: LocalConfig) -> FileSecretResolver:
    return FileSecretResolver(config.secret_map)


def _descriptor(connector_id: str) -> dict | None:
    path = _CONNECTORS_DIR / connector_id / "config.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def validate_against_descriptors(config: LocalConfig) -> list[str]:
    """Advisory cross-check (for ``list``): KEY-NAME-only warnings, never a secret value."""
    warns: list[str] = []
    for cid, block in config.connectors.items():
        desc = _descriptor(cid)
        if desc is None:
            warns.append(f"{cid}: no config.json descriptor")
            continue
        declared = {c["key"] for c in desc.get("credentials", [])}
        for key in set(block.get("secrets") or {}) - declared:
            warns.append(f"{cid}: secret under unknown credential key {key!r}")
    return warns


def assert_runnable(config: LocalConfig, connector_id: str) -> None:
    """Hard-fail (token-free, KEY-NAME-only) if the TARGET connector is mis-credentialed (B3).
    Required credentials are checked via the RESOLVER (env OR file), so an env-only operator passes."""
    block = config.connectors.get(connector_id)
    if not block:
        raise ConfigError(f"connector {connector_id!r} not in config")
    desc = _descriptor(connector_id)
    if desc is None:
        raise ConfigError(f"{connector_id}: no config.json descriptor")
    declared = {c["key"] for c in desc.get("credentials", [])}
    unknown = set(block.get("secrets") or {}) - declared
    if unknown:
        raise ConfigError(f"{connector_id}: secret(s) under unknown credential key(s): {sorted(unknown)}")
    resolver = resolver_from(config)
    missing = [c["key"] for c in desc.get("credentials", [])
               if c.get("required") and not resolver.resolve(c["key"])]
    if missing:
        raise ConfigError(f"{connector_id}: missing required credential(s): {sorted(missing)} "
                          f"(set in config or BICAMERAL_<KEY>)")
