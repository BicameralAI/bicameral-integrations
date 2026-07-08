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


def oauth_aux_keys(credential: dict) -> tuple[str, ...]:
    """The durable-OAuth aux secret keys for one descriptor credential (single source — #227 LD5a).

    For an ``oauth2`` credential whose refresh is operator-owned (``refresh_owner: "operator"``,
    e.g. google_drive) the durable persistence shape is THREE flat secret keys derived from the
    credential key: ``<key>_refresh_token`` + ``<key>_client_id`` + ``<key>_client_secret``
    (consumed by ``RefreshTokenSecretResolver`` — FX-RUNTIME-006). Every consumer (gate below,
    advisory check, ``cli.build_resolver``, the consent writer) derives the names HERE; none
    restates the suffixes (SG-2026-06-12-F). Any other credential returns ``()``."""
    if credential.get("type") == "oauth2" and credential.get("refresh_owner") == "operator":
        key = credential["key"]
        return (f"{key}_refresh_token", f"{key}_client_id", f"{key}_client_secret")
    return ()


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
        for cred in desc.get("credentials", []):
            declared.update(oauth_aux_keys(cred))  # durable-OAuth triple is a known shape, not a typo
        for key in set(block.get("secrets") or {}) - declared:
            warns.append(f"{cid}: secret under unknown credential key {key!r}")
    return warns


def assert_runnable(config: LocalConfig, connector_id: str, *, mode: str = "active") -> None:
    """Hard-fail (token-free, KEY-NAME-only) if the TARGET connector is mis-credentialed for ``mode``.
    Required credentials are checked via the RESOLVER (env OR file), so an env-only operator passes.
    **Mode-scoped (FX-RUNTIME-005):** only credentials serving ``mode`` are required — a credential's
    ``modes`` that is absent OR empty means **all modes** (``mode in (c.get("modes") or [mode])``), so an
    active ``run`` does not demand a credential that only serves the webhook-receive path. The unknown-key
    rejection below is mode-INDEPENDENT (a typo'd key hard-fails on any mode)."""
    block = config.connectors.get(connector_id)
    if not block:
        raise ConfigError(f"connector {connector_id!r} not in config")
    desc = _descriptor(connector_id)
    if desc is None:
        raise ConfigError(f"{connector_id}: no config.json descriptor")
    declared = {c["key"] for c in desc.get("credentials", [])}
    for cred in desc.get("credentials", []):
        declared.update(oauth_aux_keys(cred))  # LD5a: the refresh triple is declared shape (audit #230 F1)
    unknown = set(block.get("secrets") or {}) - declared
    if unknown:
        raise ConfigError(f"{connector_id}: secret(s) under unknown credential key(s): {sorted(unknown)}")
    # Runtime-key allowlist (purple-team CONFIG, 2026-06-11): an operator runtime sub-key not
    # declared in the descriptor's runtime_config is rejected, so a credentialed builder kwarg
    # (e.g. linear's `endpoint`) cannot be silently widened/overridden via local config.
    declared_runtime = {rc["key"] for rc in desc.get("runtime_config", [])}
    unknown_runtime = set(block.get("runtime") or {}) - declared_runtime
    if unknown_runtime:
        raise ConfigError(
            f"{connector_id}: runtime key(s) not declared in descriptor runtime_config: "
            f"{sorted(unknown_runtime)}"
        )
    resolver = resolver_from(config)
    missing = []
    for c in desc.get("credentials", []):
        if not (c.get("required") and mode in (c.get("modes") or [mode])):
            continue
        if resolver.resolve(c["key"]):
            continue  # direct value (pasted token / api key) satisfies
        aux = oauth_aux_keys(c)
        if aux and all(resolver.resolve(k) for k in aux):
            continue  # durable path: full refresh triple satisfies (LD5a; partial triple fails closed)
        missing.append(c["key"])
    if missing:
        raise ConfigError(f"{connector_id}: missing required credential(s): {sorted(missing)} "
                          f"(set in config or BICAMERAL_<KEY>)")
