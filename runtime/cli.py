# SPDX-License-Identifier: MIT
"""Headless operator runner: ``python -m runtime.cli list|run|run-mods`` (ADR-0016 / FX-RUNTIME-004).

Drives connectors + mods from the operator-local config WITHOUT the mcp UI. Default sink is a local
``CollectingSink`` (prints screened emissions — never a secret); ``--sink gateway`` does a real POST
(default-gated). The testable core (`run_connector`/`run_mods`) takes an injected transport+sink so
tests drive a ``RecordedTransport`` (a mock does NOT promote to Live — ADR-0012). Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import sys

from mods.contract import run_mod

from .local_config import (
    ConfigError,
    DEFAULT_CONFIG,
    LocalConfig,
    assert_runnable,
    load_config,
    resolver_from,
    validate_against_descriptors,
)
from .poll_auth import PollError
from .poll_client import HttpTransport, UrllibTransport
from .runner_registry import RUNNERS, load_mod
from .sinks import CollectingSink, EmissionSink, GatewayEmissionGated, GatewaySink


def run_connector(
    connector_id: str,
    config: LocalConfig,
    transport: HttpTransport,
    sink: EmissionSink,
    *,
    document_id: str = "",
    limit: int | None = None,
) -> int:
    """Dispatch a connector's ACTIVE fetch to the sink. Fail-closed on unknown/mis-credentialed target."""
    runner = RUNNERS.get(connector_id)
    if runner is None:
        raise ConfigError(f"unknown or not-runnable connector: {connector_id!r}")
    assert_runnable(config, connector_id)  # B3: hard-fail (token-free) on a bad credential key
    runtime = (config.connectors.get(connector_id) or {}).get("runtime", {})
    count = runner(resolver_from(config), runtime, document_id, transport, sink)
    if limit is not None and isinstance(sink, CollectingSink) and len(sink.emissions) > limit:
        del sink.emissions[limit:]  # --limit caps PRINTED emissions (the fetch still walks fully)
        count = limit
    return count


def run_mods(connector_id: str, config: LocalConfig, transport: HttpTransport, mods: list[str]) -> dict:
    """Run a connector to a local sink, then pipe its emissions through each mod. {mod_id: emissions}."""
    sink = CollectingSink()
    run_connector(connector_id, config, transport, sink)
    out: dict[str, list] = {}
    for mod_id in mods:
        mod, manifest = load_mod(mod_id)
        out[mod_id] = run_mod(mod, sink.emissions, manifest)
    return out


def _enabled_mods(config: LocalConfig) -> list[str]:
    return [mid for mid, blk in config.mods.items() if (blk or {}).get("enabled")]


def _print_emissions(sink: CollectingSink) -> None:
    for em in sink.emissions:  # screened by FX-SEC-001 before emit — no secret here
        excerpt = em.evidence[0].excerpt if em.evidence else ""
        print(json.dumps({"source_id": em.source_id, "title": em.title, "excerpt": excerpt}))


def _cmd_list(config: LocalConfig) -> int:
    for cid, blk in config.connectors.items():
        flags = ("enabled" if (blk or {}).get("enabled") else "disabled",
                 "runnable" if cid in RUNNERS else "not-runnable")
        print(f"connector {cid}: {', '.join(flags)}")
    for mid in _enabled_mods(config):
        print(f"mod {mid}: enabled")
    for warn in validate_against_descriptors(config):
        print(f"warning: {warn}", file=sys.stderr)
    return 0


def _make_sink(kind: str, config: LocalConfig) -> EmissionSink:
    if kind == "gateway":
        gw = config.gateway
        return GatewaySink(endpoint=gw.get("endpoint", ""), token=gw.get("token", ""))
    return CollectingSink()


def _cmd_run(config: LocalConfig, args: argparse.Namespace) -> int:
    sink = _make_sink(args.sink, config)
    count = run_connector(args.connector, config, UrllibTransport(), sink,
                          document_id=args.document_id or "", limit=args.limit)
    if isinstance(sink, CollectingSink):
        _print_emissions(sink)
    print(f"emitted {count}", file=sys.stderr)
    return 0


def _cmd_run_mods(config: LocalConfig, args: argparse.Namespace) -> int:
    mods = args.mods.split(",") if args.mods else _enabled_mods(config)
    results = run_mods(args.connector, config, UrllibTransport(), mods)
    for mod_id, emissions in results.items():
        for me in emissions:
            art = me.advisory or me.routing_hint
            print(json.dumps({"mod": mod_id, "output_type": me.output_type,
                              "message": getattr(art, "message", getattr(art, "reason", ""))}))
    return 0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="runtime.cli", description="Headless connector/mod runner")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    run = sub.add_parser("run")
    run.add_argument("connector")
    run.add_argument("--document-id", default="")
    run.add_argument("--sink", choices=["local", "gateway"], default="local")
    run.add_argument("--limit", type=int, default=None)
    rm = sub.add_parser("run-mods")
    rm.add_argument("connector")
    rm.add_argument("--mods", default="")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "list":
            return _cmd_list(config)
        if args.command == "run":
            return _cmd_run(config, args)
        return _cmd_run_mods(config, args)
    except (ConfigError, PollError, GatewayEmissionGated, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)  # str(exc) only — NEVER repr(config)/gateway (token)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
