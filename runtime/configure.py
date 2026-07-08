# SPDX-License-Identifier: MIT
"""Config-on-rails: ``python -m runtime.cli configure <connector>`` (ADR-0016 / FX-RUNTIME-005/006).

The terminal equivalent of the mcp UI config wizard (``docs/UI_RENDERING_SPEC.md``): reads a
connector's descriptor (``connectors/<id>/config.json`` — no vendoring), walks its ordered
``instructions[]``, and switches on ``action`` to guide an operator through populating the gitignored
``config/bicameral.local.json`` that ``FileSecretResolver`` already reads. All six action types
(``open_url`` / ``paste_secret`` / ``oauth_consent`` / ``register_webhook`` / ``configure`` / ``verify``)
are handled generically from the descriptor.

Security posture (matches ADR-0016): stdlib-only; secrets are entered through a MASKED prompt, are
NEVER echoed/logged, and are written ONLY to the operator's gitignored local config. The
credential set is **mode-scoped** (FX-RUNTIME-005): a credential's ``modes`` selects whether it is
required for the run being configured. OAuth uses a loopback redirect catcher + the stdlib refresh
grant (FX-RUNTIME-006); a pasted access token is an explicit ~1h TEST escape hatch, not durable.
"""

from __future__ import annotations

import getpass
import json
import re
import urllib.parse
import webbrowser
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .google_oauth import RefreshTokenSecretResolver
from .local_config import ConfigError, load_config
from .poll_auth import PollError
from .poll_client import HttpTransport, UrllibTransport
from .sinks import CollectingSink

_REPO = Path(__file__).resolve().parents[1]
_CONNECTORS_DIR = _REPO / "connectors"
_EXAMPLE_CONFIG = _REPO / "config" / "bicameral.example.json"

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # nosec B105 — an endpoint URL, not a secret

_PASTE_TYPES = frozenset({"api_key", "webhook_secret", "basic"})

# A build_auth_url takes the loopback redirect_uri and returns the provider consent URL; the catcher
# returns (auth_code, redirect_uri). Injectable so tests stub the browser + loopback (ADR-0012).
CodeCatcher = Callable[[Callable[[str], str]], "tuple[str, str]"]


@dataclass
class ConfigureIO:
    """Injectable I/O seam for the wizard so tests drive it without a TTY, browser, or live network."""

    prompt: Callable[[str], str] = (
        input  # visible input (Enter, URLs, typed runtime values)
    )
    secret_prompt: Callable[[str], str] = getpass.getpass  # MASKED input (never echoed)
    out: Callable[[str], None] = print
    open_browser: Callable[[str], bool] = webbrowser.open
    transport: HttpTransport = field(default_factory=UrllibTransport)
    catch_code: CodeCatcher | None = (
        None  # None -> the real loopback catcher (bound to out/open_browser)
    )


def _load_descriptor(connector_id: str) -> dict:
    """Read ``connectors/<id>/config.json``; a missing/invalid id fails closed with a clean error."""
    if not re.fullmatch(r"[a-z0-9_]+", connector_id or ""):
        raise ConfigError(f"unknown connector: {connector_id!r}")
    path = _CONNECTORS_DIR / connector_id / "config.json"
    if not path.exists():
        raise ConfigError(
            f"unknown connector: {connector_id!r} (no {path.relative_to(_REPO)})"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _serves(cred: dict, selected: list[str], connector_modes: list[str]) -> bool:
    """A credential serves the run when its ``modes`` (absent/empty = all modes) intersect ``selected``."""
    cred_modes = cred.get("modes") or connector_modes
    return bool(set(cred_modes) & set(selected))


def _coerce(raw_val: str, default: object) -> object:
    """Type a typed ``runtime_config`` value off the descriptor default (bool/int/float/str)."""
    if isinstance(default, bool):
        return raw_val.strip().lower() in {"1", "true", "yes", "y", "on"}
    if isinstance(default, int):
        return int(raw_val)
    if isinstance(default, float):
        return float(raw_val)
    return raw_val


def _pop_first(items: "deque[dict]", pred: Callable[[dict], bool]) -> dict | None:
    """Remove + return the first entry matching ``pred`` (order preserved), or ``None``."""
    for i, item in enumerate(items):
        if pred(item):
            del items[i]
            return item
    return None


class Configurator:
    """Walks a connector descriptor's ``instructions[]`` and populates the operator-local config."""

    def __init__(self, io: ConfigureIO | None = None) -> None:
        self._io = io or ConfigureIO()

    # --- file I/O -------------------------------------------------------------------------------
    def _load_raw(self, path: str | Path) -> tuple[dict, bool]:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")), False
        return json.loads(_EXAMPLE_CONFIG.read_text(encoding="utf-8")), True

    def _write(self, path: str | Path, raw: dict) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    # --- entrypoint -----------------------------------------------------------------------------
    def configure(
        self,
        connector_id: str,
        config_path: str | Path,
        *,
        modes: list[str] | None = None,
        paste_token: bool = False,
    ) -> int:
        desc = _load_descriptor(connector_id)
        connector_modes = list(desc.get("modes") or [])
        selected = list(modes) if modes else list(connector_modes)
        bad = [m for m in selected if m not in connector_modes]
        if bad:
            raise ConfigError(
                f"{connector_id}: unknown mode(s) {sorted(bad)}; supported: {connector_modes}"
            )

        raw, created = self._load_raw(config_path)
        if created:
            self._io.out(
                f"(creating {Path(config_path)} from bicameral.example.json — gitignored)"
            )
        connectors = raw.setdefault("connectors", {})
        block = connectors.setdefault(connector_id, {})
        if created:
            # the example is a template; drop its placeholder secrets/runtime for the target so only
            # values we actually collect persist. An EXISTING file is merged (prior values are kept).
            block["secrets"] = {}
            block["runtime"] = {}
        block.setdefault("secrets", {})
        block.setdefault("runtime", {})

        credentials = desc.get("credentials", [])
        pastable = deque(
            c
            for c in credentials
            if c.get("type") in _PASTE_TYPES and _serves(c, selected, connector_modes)
        )
        oauth = deque(
            c
            for c in credentials
            if c.get("type") == "oauth2" and _serves(c, selected, connector_modes)
        )

        self._io.out(
            f"Configuring '{connector_id}' — modes: {', '.join(selected) or '(none)'}"
        )
        for instr in desc.get("instructions", []):
            action = instr.get("action")
            if action == "open_url":
                self._do_open_url(instr)
            elif action == "paste_secret":
                self._do_paste_secret(instr, pastable, block)
            elif action == "oauth_consent":
                self._do_oauth_consent(instr, oauth, block, paste_token)
            elif action == "register_webhook":
                self._do_register_webhook(instr, selected, pastable, block)
            elif action == "configure":
                self._do_configure(instr, desc, block)
            elif action == "verify":
                self._write(
                    config_path, raw
                )  # flush so load_config sees the just-entered secrets
                self._do_verify(instr, connector_id, config_path)

        block["enabled"] = True
        self._write(config_path, raw)
        self._io.out(
            f"Done. '{connector_id}' is enabled in {Path(config_path)} (secrets stored, never logged)."
        )
        return 0

    # --- per-action handlers --------------------------------------------------------------------
    def _do_open_url(self, instr: dict) -> None:
        self._io.out(instr.get("text", ""))
        link = instr.get("link")
        if link:
            self._io.out(f"  Open: {link}")
        self._io.prompt("  Press Enter when done... ")

    def _prompt_and_store_secret(self, cred: dict, text: str, block: dict) -> None:
        key = cred["key"]
        label = cred.get("label", key)
        if text:
            self._io.out(text)
        header = cred.get("header")
        if header:
            self._io.out(f"  Sent as: {header}")
        regex = cred.get("validation")
        for _ in range(3):
            value = self._io.secret_prompt(f"  {label} (hidden): ").strip()
            if not value:
                self._io.out("  no value entered; try again.")
                continue
            if regex and not re.search(regex, value):
                self._io.out(
                    "  value does not match the required format; not stored (value hidden)."
                )
                continue
            block.setdefault("secrets", {})[key] = value
            self._io.out(f"  stored credential '{key}' (value hidden).")
            return
        raise ConfigError(f"{key}: no valid value provided")

    def _do_paste_secret(
        self, instr: dict, pastable: "deque[dict]", block: dict
    ) -> None:
        if not pastable:
            self._io.out(
                "  (skipped: no remaining credential for this step under the selected modes)"
            )
            return
        self._prompt_and_store_secret(pastable.popleft(), instr.get("text", ""), block)

    def _do_register_webhook(
        self, instr: dict, selected: list[str], pastable: "deque[dict]", block: dict
    ) -> None:
        if "webhook" not in selected:
            self._io.out(
                "  (skipped register_webhook: 'webhook' not in the selected modes)"
            )
            _pop_first(
                pastable, lambda c: c.get("type") == "webhook_secret"
            )  # keep paste ordering aligned
            return
        self._io.out(instr.get("text", ""))
        link = instr.get("link")
        if link:
            self._io.out(f"  Provider webhook setup: {link}")
        receiver = self._io.prompt(
            "  Your Bicameral webhook receiver URL (operator-provisioned): "
        ).strip()
        if receiver:
            self._io.out(
                f"  Paste THIS receiver URL into the provider's webhook config: {receiver}"
            )
        cred = _pop_first(pastable, lambda c: c.get("type") == "webhook_secret")
        if cred is None:
            self._io.out(
                "  (no webhook signing-secret credential to store for the selected modes)"
            )
            return
        self._prompt_and_store_secret(
            cred,
            f"Paste the signing secret the provider shows for '{cred.get('label', cred['key'])}'.",
            block,
        )

    def _do_configure(self, instr: dict, desc: dict, block: dict) -> None:
        self._io.out(instr.get("text", ""))
        for rc in desc.get("runtime_config", []):
            key = rc["key"]
            label = rc.get("label", key)
            default = rc.get("default")
            required = rc.get("required", False)
            suffix = f" [{default}]" if default is not None else ""
            raw_val = self._io.prompt(f"  {label}{suffix}: ").strip()
            if not raw_val:
                if default is not None:
                    block.setdefault("runtime", {})[key] = default
                    self._io.out(f"  using default {key} = {default}")
                elif required:
                    raise ConfigError(f"{key}: a value is required")
                continue
            block.setdefault("runtime", {})[key] = _coerce(raw_val, default)
            self._io.out(f"  set {key} = {block['runtime'][key]}")

    def _do_oauth_consent(
        self, instr: dict, oauth: "deque[dict]", block: dict, paste_token: bool
    ) -> None:
        if not oauth:
            self._io.out("  (skipped: no oauth2 credential for the selected modes)")
            return
        cred = oauth.popleft()
        key = cred["key"]
        self._io.out(instr.get("text", ""))
        scopes = cred.get("scopes", [])
        if scopes:
            self._io.out(f"  Scopes: {', '.join(scopes)}")

        if paste_token:
            self._io.out(
                "  WARNING: a pasted access token is a ~1h TEST credential — NOT durable."
            )
            self._io.out(
                "  Run oauth_consent WITHOUT --paste-token for the durable refresh-token path."
            )
            for _ in range(3):
                token = self._io.secret_prompt("  Access token (hidden): ").strip()
                if token:
                    block.setdefault("secrets", {})[key] = token
                    self._io.out(
                        f"  stored '{key}' access token (hidden). Expires ~1h; re-run to refresh."
                    )
                    return
                self._io.out("  no value entered; try again.")
            raise ConfigError(f"{key}: no access token provided")

        client_id = self._io.prompt("  OAuth client id: ").strip()
        client_secret = self._io.secret_prompt(
            "  OAuth client secret (hidden): "
        ).strip()
        if not client_id or not client_secret:
            raise ConfigError(
                "oauth_consent: client id and client secret are required for the durable path"
            )

        def build_auth_url(redirect_uri: str) -> str:
            params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": " ".join(scopes),
                "access_type": "offline",  # ask Google for a refresh token
                "prompt": "consent",  # force a refresh token even on re-consent
            }
            return _GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)

        catch = self._io.catch_code or self._default_catch_code
        code, redirect_uri = catch(build_auth_url)
        tokens = self._exchange_code(
            code=code,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
        access_token = tokens.get("access_token", "")
        refresh_token = tokens.get("refresh_token", "")
        if not isinstance(access_token, str) or not access_token:
            raise ConfigError("oauth_consent: token exchange returned no access token")

        if refresh_token:
            # Durable: prove the refresh token mints a fresh access token via the stdlib resolver.
            resolver = RefreshTokenSecretResolver(
                target_key=key,
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                transport=self._io.transport,
            )
            access_token = resolver.resolve(key)
            self._io.out(
                "  durable refresh token captured and verified (mints fresh access tokens)."
            )
        else:
            self._io.out(
                "  NOTE: no refresh token returned (Google returns it only on first consent)."
            )

        block.setdefault("secrets", {})[key] = access_token
        self._io.out(f"  stored '{key}' access token (hidden).")
        self._io.out(
            "  Durability: the STORED value is a short-lived (~1h) access token; the DURABLE"
        )
        self._io.out("  credential is the OAuth refresh token. For unattended use wire")
        self._io.out(
            "  runtime.RefreshTokenSecretResolver (refresh token + client id/secret) —"
        )
        self._io.out(
            "  see docs/runbooks/golive-google_drive.md. A pasted/stored access token expires in ~1h."
        )

    def _exchange_code(
        self, *, code: str, client_id: str, client_secret: str, redirect_uri: str
    ) -> dict:
        """POST the authorization-code grant to Google's token endpoint (stdlib; token-safe errors)."""
        body = urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            resp = self._io.transport.request(
                "POST", _GOOGLE_TOKEN_URL, headers=headers, body=body
            )
        except Exception:  # noqa: BLE001 — a urllib exc message can embed the POST body (the secrets)
            raise ConfigError("oauth_consent: token exchange transport error") from None
        if resp.status != 200:
            raise ConfigError(
                f"oauth_consent: token exchange failed (status={resp.status})"
            )  # body dropped
        try:
            parsed = json.loads(resp.body)
        except (ValueError, UnicodeDecodeError):
            raise ConfigError(
                "oauth_consent: token exchange returned an unparseable body"
            ) from None
        if not isinstance(parsed, dict):
            raise ConfigError(
                "oauth_consent: token exchange returned a non-object body"
            )
        return parsed

    def _default_catch_code(
        self, build_auth_url: Callable[[str], str]
    ) -> tuple[str, str]:
        """Real loopback catcher: bind 127.0.0.1:<ephemeral>, open the browser, capture ``?code=``."""
        import http.server  # stdlib; imported lazily so tests never touch the network stack

        holder: dict[str, str] = {}

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 (stdlib handler contract)
                params = dict(
                    urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query)
                )
                if "code" in params or "error" in params:
                    holder.update(params)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<html><body>Bicameral: authorization received. "
                    b"Close this tab and return to the terminal.</body></html>"
                )

            def log_message(
                self, *_args: object
            ) -> None:  # silence the default stderr access log
                return

        server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        redirect_uri = f"http://127.0.0.1:{server.server_address[1]}/"
        auth_url = build_auth_url(redirect_uri)
        self._io.out(
            "  Opening your browser to grant access. If it does not open, visit:"
        )
        self._io.out(f"    {auth_url}")
        try:
            self._io.open_browser(auth_url)
        except Exception:  # noqa: BLE001 — a headless box has no browser; the operator uses the printed URL
            pass
        server.timeout = 300.0
        for _ in range(
            50
        ):  # bounded: ignore favicon/preflight hits until the redirect carries the code
            if holder.get("code") or holder.get("error"):
                break
            server.handle_request()
        server.server_close()
        if holder.get("error"):
            raise ConfigError(
                f"oauth_consent: provider returned error '{holder['error']}'"
            )
        code = holder.get("code", "")
        if not code:
            raise ConfigError(
                "oauth_consent: no authorization code received before timeout"
            )
        return code, redirect_uri

    def _do_verify(
        self, instr: dict, connector_id: str, config_path: str | Path
    ) -> bool:
        from .cli import (
            run_connector,
        )  # local import avoids a cli <-> configure import cycle

        self._io.out(instr.get("text", ""))
        try:
            cfg = load_config(config_path)
            sink = CollectingSink()
            count = run_connector(connector_id, cfg, self._io.transport, sink)
        except (
            ConfigError,
            PollError,
        ) as exc:  # messages are token-free by design (ADR-0016)
            self._io.out(f"  verify: FAIL — {exc}")
            return False
        self._io.out(
            f"  verify: PASS — {count} emission(s) fetched through the harness transport."
        )
        return True


__all__ = ["Configurator", "ConfigureIO"]
