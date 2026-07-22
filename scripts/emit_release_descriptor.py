#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Emit and verify a commit-bound Integrations release descriptor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"^[a-f0-9]{40}$")
DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")


def tree_digest(paths: list[str]) -> str:
    hasher = hashlib.sha256()
    count = 0
    for root_name in sorted(paths):
        root = ROOT / root_name
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            count += 1
            hasher.update(path.relative_to(ROOT).as_posix().encode())
            hasher.update(b"\0")
            hasher.update(path.read_bytes())
    if not count:
        raise ValueError("descriptor input paths contain no files")
    return "sha256:" + hasher.hexdigest()


def canonical_digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def build_descriptor(commit: str) -> dict:
    if not SHA.fullmatch(commit):
        raise ValueError("commit must be a full lowercase git SHA")
    payload = {
        "schema_version": 1,
        "component": "integrations",
        "commit": commit,
        "artifacts": {
            "runtime": tree_digest(["adapter", "connectors", "runtime"]),
            "mods": tree_digest(["mods"]),
        },
        "interfaces": {
            "bot_ingress": tree_digest(["adapter/core", "protocol/provider_acquisition"]),
            "runtime_schema": tree_digest(["runtime/schemas"]),
        },
    }
    payload["descriptor_digest"] = canonical_digest(payload)
    return payload


def validate_descriptor(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["descriptor must be an object"]
    errors: list[str] = []
    if payload.get("schema_version") != 1 or payload.get("component") != "integrations":
        errors.append("schema/component mismatch")
    if not isinstance(payload.get("commit"), str) or not SHA.fullmatch(payload["commit"]):
        errors.append("commit must be a full lowercase git SHA")
    for section in ("artifacts", "interfaces"):
        values = payload.get(section)
        if not isinstance(values, dict) or not values:
            errors.append(f"{section} must be non-empty")
            continue
        for name, value in values.items():
            if not isinstance(value, str) or not DIGEST.fullmatch(value):
                errors.append(f"{section}.{name} must be a sha256 digest")
    unsigned = {key: value for key, value in payload.items() if key != "descriptor_digest"}
    if payload.get("descriptor_digest") != canonical_digest(unsigned):
        errors.append("descriptor_digest does not bind the descriptor")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "release-artifacts" / "integrations-release-descriptor.json")
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        errors = validate_descriptor(json.loads(args.verify.read_text()))
        if errors:
            print("\n".join(f"- {error}" for error in errors))
            return 1
        return 0
    commit = os.environ.get("RELEASE_SOURCE_COMMIT") or os.environ.get("GITHUB_SHA")
    if not commit:
        parser.error("RELEASE_SOURCE_COMMIT or GITHUB_SHA is required")
    args.output.parent.mkdir(exist_ok=True)
    args.output.write_text(json.dumps(build_descriptor(commit), indent=2, sort_keys=True) + "\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
