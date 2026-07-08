# SPDX-License-Identifier: MIT
"""Config-on-rails: ``python -m runtime.cli configure <connector>`` (#227; FX-RUNTIME-007).

Walks the connector descriptor's ordered ``instructions[]`` in the terminal — the text-mode
equivalent of ``docs/UI_RENDERING_SPEC.md`` — collecting credentials (masked, validated,
mode-scoped per FX-RUNTIME-005) and runtime config into the operator-local store via the atomic
writer (``config_write``). Secrets are read with ``getpass`` at the CLI edge only, never echoed,
logged, or embedded in an error. This module never imports ``runtime.cli`` — the ``verify``
harness is INJECTED as ``verify_fn`` (LD1; keeps ``cli -> configure`` one-way). Stdlib-only.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Callable

from .config_write import write_local_config
from .google_oauth import OAuthRefreshError
from .local_config import ConfigError, _descriptor, load_config, oauth_aux_keys
from .oauth_consent import run_consent
from .poll_auth import PollError
from .poll_client import HttpTransport
from .sinks import CollectingSink

_ENV_PREFIX = "BICAMERAL_"


@dataclass
class ConfigureIO:
    """Injectable interaction seams (tests script these; the CLI edge passes real ones)."""

    input_fn: Callable[[str], str]
    getpass_fn: Callable[[str], str]
    open_url_fn: Callable[[str], object]


@dataclass
class _Walk:
    """Mutable state threaded through one configure run."""

    connector_id: str
    desc: dict
    config_path: str
    io: ConfigureIO
    transport: HttpTransport
    verify_fn: Callable[..., int] | None
    modes: set[str]
    paste_token: bool
    secrets: dict[str, str] = field(default_factory=dict)
    runtime: dict[str, object] = field(default_factory=dict)
    queue: list[dict] = field(default_factory=list)


def _selected_modes(desc: dict, modes_arg: str) -> set[str]:
    """LD4: requested modes (validated) or the union declared across the descriptor's credentials."""
    declared: set[str] = set()
    for cred in desc.get("credentials", []):
        declared.update(cred.get("modes") or desc.get("modes") or [])
    declared.update(desc.get("modes") or [])
    if not modes_arg:
        return declared
    requested = {m.strip() for m in modes_arg.split(",") if m.strip()}
    unknown = requested - declared
    if unknown:
        raise ConfigError(f"unknown mode(s) for {desc.get('id')!r}: {sorted(unknown)}")
    return requested


def _in_scope(cred: dict, modes: set[str], desc: dict) -> bool:
    return bool(set(cred.get("modes") or desc.get("modes") or modes) & modes)


def _pop_credential(walk: _Walk, *, cred_type: str | None = None) -> dict | None:
    """LD3: consume the next in-scope credential (declared order); optionally by type."""
    for i, cred in enumerate(walk.queue):
        if cred_type is None or cred.get("type") == cred_type:
            return walk.queue.pop(i)
    return None


def _prompt_secret(walk: _Walk, cred: dict) -> str:
    """Masked, validated, re-prompting collection of one credential value. Never echoes."""
    pattern = cred.get("validation", "")
    while True:
        value = walk.io.getpass_fn(f"{cred.get('label', cred['key'])} (input hidden): ")
        if not value:
            print("Empty value — please paste the credential.")
            continue
        if pattern and not re.fullmatch(pattern, value):
            print(f"Value does not match the expected format for {cred.get('label', cred['key'])} "
                  f"(check for an accidental prefix such as 'Bearer '); not stored. Try again.")
            continue
        return value


def _do_paste_secret(walk: _Walk, step: dict, *, after_webhook: bool) -> None:
    # LD3 adjacency: a paste_secret immediately following register_webhook binds THE webhook
    # credential — when that credential is out of scope (--modes active) the step is SKIPPED,
    # never re-bound to the next credential (zendesk-class descriptors; review F2).
    cred = _pop_credential(walk, cred_type="webhook_secret" if after_webhook else None)
    if cred is None:
        return  # intended credential out of scope or already collected
    print(step.get("text", ""))
    walk.secrets[cred["key"]] = _prompt_secret(walk, cred)


def _do_register_webhook(walk: _Walk, step: dict) -> None:
    if not any(c.get("type") == "webhook_secret" for c in walk.queue):
        print("(webhook mode not selected — skipping webhook registration)")
        return
    print(step.get("text", ""))
    if step.get("link"):
        print(f"  provider setup: {step['link']}")
    receiver = walk.io.input_fn("Your Bicameral webhook receiver URL (operator-provisioned): ").strip()
    declared_runtime = {rc["key"] for rc in walk.desc.get("runtime_config", [])}
    if "webhook_receiver" in declared_runtime:
        walk.runtime["webhook_receiver"] = receiver
    print(f"Paste this receiver URL into the provider's webhook form: {receiver}")


def _do_configure(walk: _Walk, step: dict) -> None:
    print(step.get("text", ""))
    for rc in walk.desc.get("runtime_config", []):
        default = rc.get("default")
        suffix = f" [{default}]" if default is not None else ""
        while True:
            raw = walk.io.input_fn(f"{rc.get('label', rc['key'])}{suffix}: ").strip()
            if not raw and default is not None:
                walk.runtime[rc["key"]] = default
                break
            if not raw and rc.get("required"):
                print(f"{rc['key']} is required — please provide a value.")  # audit #231 A2
                continue
            if raw:
                try:
                    walk.runtime[rc["key"]] = int(raw) if isinstance(default, int) else raw
                except ValueError:
                    print(f"{rc['key']} expects a number — try again.")
                    continue
            break


def _do_oauth_consent(walk: _Walk, step: dict) -> None:
    cred = _pop_credential(walk, cred_type="oauth2")
    if cred is None:
        return
    print(step.get("text", ""))
    if walk.paste_token:
        print("WARNING: a pasted access token is a ~1h TEST credential, NOT durable — the durable "
              "path is the OAuth consent flow (refresh token) or a service-account JSON.")
        walk.secrets[cred["key"]] = _prompt_secret(walk, cred)
        return
    aux = oauth_aux_keys(cred)
    if not aux:
        raise ConfigError(f"{walk.connector_id}: oauth2 credential without operator refresh_owner "
                          f"is not supported by configure")
    client_id = walk.io.input_fn("OAuth client id: ").strip()
    client_secret = walk.io.getpass_fn("OAuth client secret (input hidden): ")
    refresh = run_consent(client_id=client_id, client_secret=client_secret,
                          scopes=list(cred.get("scopes") or []), transport=walk.transport,
                          open_url_fn=walk.io.open_url_fn)
    walk.secrets.update(dict(zip(aux, (refresh, client_id, client_secret))))
    print("Refresh token received and stored (durable credential; access tokens are minted per run).")


def _persist(walk: _Walk, *, enabled: bool) -> None:
    def mutate(doc: dict) -> None:
        block = doc.setdefault("connectors", {}).setdefault(walk.connector_id, {})
        block["secrets"] = {**(block.get("secrets") or {}), **walk.secrets}
        if walk.runtime:
            block["runtime"] = {**(block.get("runtime") or {}), **walk.runtime}
        block["enabled"] = enabled

    write_local_config(walk.config_path, mutate)
    for key in walk.secrets:
        if os.environ.get(_ENV_PREFIX + key.upper()):
            print(f"warning: env var {_ENV_PREFIX + key.upper()} is set and OVERRIDES the value "
                  f"just written to the config file", file=sys.stderr)


def _do_verify(walk: _Walk, step: dict) -> int:
    print(step.get("text", ""))
    if "active" not in walk.modes or walk.verify_fn is None:
        # no active mode selected, OR the connector has no CLI-runnable active fetch (review F3):
        # webhook delivery verifies at the operator's receiver, not from the sender side.
        print("(active verify not available here — webhook delivery verifies at your receiver; "
              "see the connector's SETUP.md)")
        return 0
    _persist(walk, enabled=False)  # verify runs against the REAL persisted config
    config = load_config(walk.config_path)
    document_id = str(walk.runtime.get("document_id", ""))
    try:
        count = walk.verify_fn(walk.connector_id, config, walk.transport, CollectingSink(),
                               document_id=document_id)
    except (PollError, ConfigError, OAuthRefreshError) as exc:
        print(f"verify FAILED: {exc}", file=sys.stderr)  # token-free by contract of these errors
        return 1
    print(f"verify PASSED: {count} emission(s)")
    return 0


def run_configure(connector_id: str, config_path: str, *, modes: str = "",
                  io: ConfigureIO, transport: HttpTransport,
                  verify_fn: Callable[..., int] | None = None,
                  paste_token: bool = False) -> int:
    """Walk the descriptor's instructions[]; persist credentials + runtime config; 0 on success."""
    desc = _descriptor(connector_id)
    if desc is None:
        raise ConfigError(f"unknown connector: {connector_id!r}")
    selected = _selected_modes(desc, modes)
    walk = _Walk(connector_id=connector_id, desc=desc, config_path=config_path, io=io,
                 transport=transport, verify_fn=verify_fn, modes=selected, paste_token=paste_token,
                 queue=[c for c in desc.get("credentials", []) if _in_scope(c, selected, desc)])
    print(f"Configuring {desc.get('name', connector_id)} (modes: {', '.join(sorted(selected))})")
    prev_action = ""
    for step in desc.get("instructions", []):
        action = step.get("action")
        if action == "open_url":
            print(f"{step.get('text', '')}\n  {step.get('link', '')}")
            walk.io.input_fn("Press Enter when done: ")
        elif action == "paste_secret":
            _do_paste_secret(walk, step, after_webhook=prev_action == "register_webhook")
        elif action == "register_webhook":
            _do_register_webhook(walk, step)
        elif action == "configure":
            _do_configure(walk, step)
        elif action == "oauth_consent":
            _do_oauth_consent(walk, step)
        elif action == "verify":
            rc = _do_verify(walk, step)
            if rc != 0:
                return rc
        else:  # the descriptor schema enum forbids this; fail closed anyway
            raise ConfigError(f"{connector_id}: unsupported instruction action {action!r}")
        prev_action = action or ""
    _persist(walk, enabled=True)
    print(f"{connector_id} configured and enabled.")
    return 0


__all__ = ["ConfigureIO", "run_configure"]
