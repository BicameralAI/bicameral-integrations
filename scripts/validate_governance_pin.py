# SPDX-License-Identifier: MIT
"""Inter-repo contract provenance + drift gate (#251).

Validates `docs/governance/PIN.json` — the immutable provenance record for shared
inter-repo contracts consumed by this repo (bicameral-factory#243 §5):

1. **Provenance completeness**: the pinned factory governance-doctrine commit is a
   40-char SHA; each doctrine entry and each shared contract records producer,
   consumer, upstream repo/path, and a 40-char upstream commit.
2. **Ownership**: every shared contract declares an explicit producer and consumer
   (who owns vs who consumes the contract).
3. **Drift**: any shared contract that pins a local mirror (`local_path`) must match
   its recorded `content_sha256`; a mismatch means the vendored copy drifted from the
   pinned upstream revision.
4. **Consistency**: the vendored ingest-schema contract agrees with
   `runtime/schemas/ingest_schema_pin.json` (single source of the pin).

Stdlib only; no live network. Exit 0 on success, exit 1 on any drift/provenance error.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN_PATH = ROOT / "docs" / "governance" / "PIN.json"
INGEST_PIN_PATH = ROOT / "runtime" / "schemas" / "ingest_schema_pin.json"

_CONTRACT_KEYS = (
    "contract_id",
    "producer",
    "consumer",
    "upstream_repo",
    "upstream_path",
    "upstream_commit",
)


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(c in "0123456789abcdef" for c in value)
    )


def _check_factory_governance(fg: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(fg, dict):
        return ["factory_governance: missing or not an object"]
    for key in ("producer", "consumer"):
        if not fg.get(key):
            errors.append(f"factory_governance: missing {key!r}")
    if not _is_sha(fg.get("commit")):
        errors.append("factory_governance.commit must be a 40-char lowercase SHA")
    doctrine = fg.get("doctrine")
    if not isinstance(doctrine, list) or not doctrine:
        errors.append("factory_governance.doctrine must be a non-empty list")
        return errors
    for i, entry in enumerate(doctrine):
        if not isinstance(entry, dict) or not entry.get("path"):
            errors.append(f"factory_governance.doctrine[{i}]: missing path")
        sha = entry.get("sha256") if isinstance(entry, dict) else None
        if not isinstance(sha, str) or len(sha) != 64:
            errors.append(
                f"factory_governance.doctrine[{i}]: sha256 must be a 64-char digest"
            )
    return errors


def _check_contract(i: int, contract: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return [f"shared_contracts[{i}]: not an object"]
    cid = contract.get("contract_id", i)
    for key in _CONTRACT_KEYS:
        if not contract.get(key):
            errors.append(f"shared_contracts[{cid}]: missing {key!r}")
    if not _is_sha(contract.get("upstream_commit")):
        errors.append(
            f"shared_contracts[{cid}]: upstream_commit must be a 40-char lowercase SHA"
        )
    local_path = contract.get("local_path")
    content_sha = contract.get("content_sha256")
    if local_path:
        mirror = ROOT / local_path
        if not mirror.exists():
            errors.append(
                f"shared_contracts[{cid}]: local_path not found: {local_path}"
            )
        elif not isinstance(content_sha, str) or len(content_sha) != 64:
            errors.append(
                f"shared_contracts[{cid}]: local mirror requires a 64-char content_sha256"
            )
        else:
            actual = hashlib.sha256(mirror.read_bytes()).hexdigest()
            if actual != content_sha:
                errors.append(
                    f"shared_contracts[{cid}]: drift — {local_path} sha256 is {actual}, "
                    f"pin records {content_sha}. Re-pin after a reviewed upstream sync."
                )
    return errors


def _check_ingest_consistency(contracts: list) -> list[str]:
    if not INGEST_PIN_PATH.exists():
        return [f"ingest pin not found: {INGEST_PIN_PATH}"]
    ingest = json.loads(INGEST_PIN_PATH.read_text(encoding="utf-8"))
    match = next(
        (
            c
            for c in contracts
            if isinstance(c, dict)
            and c.get("contract_id") == "external-ingest-envelope-v2"
        ),
        None,
    )
    if match is None:
        return ["shared_contracts: missing external-ingest-envelope-v2 entry"]
    errors: list[str] = []
    for key in ("upstream_commit", "content_sha256"):
        if match.get(key) != ingest.get(key):
            errors.append(
                f"external-ingest-envelope-v2 {key} ({match.get(key)}) disagrees with "
                f"runtime/schemas/ingest_schema_pin.json ({ingest.get(key)})"
            )
    return errors


def main() -> int:
    if not PIN_PATH.exists():
        print(f"governance-pin: FAIL\n  - pin not found: {PIN_PATH}")
        return 1
    pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))

    errors: list[str] = []
    errors.extend(_check_factory_governance(pin.get("factory_governance")))

    contracts = pin.get("shared_contracts")
    if not isinstance(contracts, list) or not contracts:
        errors.append("shared_contracts must be a non-empty list")
        contracts = []
    for i, contract in enumerate(contracts):
        errors.extend(_check_contract(i, contract))
    errors.extend(_check_ingest_consistency(contracts))

    if errors:
        print("governance-pin: FAIL")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(
        f"governance-pin: OK (factory doctrine pinned at {pin['factory_governance']['commit'][:12]}…, "
        f"{len(contracts)} shared contract(s) provenance + drift verified)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
