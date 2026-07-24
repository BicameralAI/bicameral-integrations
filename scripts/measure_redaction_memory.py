# SPDX-License-Identifier: MIT
"""Isolated per-candidate peak-memory measurement for the ADR-0020 spike.

``benchmark-results.json`` reports process-lifetime peak working set, which is
not attributable per candidate when several candidates run in one process.
This command measures each candidate alone in a fresh spawned interpreter:
import, initialize, run a warm medium-payload loop, then report the child's
own peak working set. Output: ``artifacts/redaction-evaluation/memory-isolated.json``.

Usage: python scripts/measure_redaction_memory.py [--out DIR] [--iterations N]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_CHILD_TEMPLATE = """\
import json, sys
from runtime.redaction_evaluation.backends import create_backend
from runtime.redaction_evaluation.bench import build_payloads
from runtime.redaction_evaluation.policy import RedactionPolicy
import psutil

policy = RedactionPolicy()
backend = create_backend({candidate_id!r})
backend.initialize()
text = build_payloads(policy)["medium"]
for _ in range({iterations}):
    backend.analyze(text, field_path="excerpt", policy=policy)
memory = psutil.Process().memory_info()
peak = getattr(memory, "peak_wset", None)
print(json.dumps({{
    "peak_bytes": int(peak) if peak else int(memory.rss),
    "basis": "peak_wset" if peak else "rss-after-loop",
}}))
"""


def measure(candidate_id: str, iterations: int) -> dict[str, object]:
    env = dict(os.environ)
    env.update({"HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"})
    script = _CHILD_TEMPLATE.format(candidate_id=candidate_id, iterations=iterations)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if completed.returncode != 0:
        return {
            "candidate_id": candidate_id,
            "status": "error",
            "returncode": completed.returncode,
        }
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    return {
        "candidate_id": candidate_id,
        "status": "ok",
        "peak_bytes": payload["peak_bytes"],
        "measurement_basis": (
            "child-process "
            + str(payload["basis"])
            + " after initialize + warm medium loop, one candidate per process"
        ),
        "iterations": iterations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="artifacts/redaction-evaluation")
    parser.add_argument("--iterations", type=int, default=30)
    args = parser.parse_args()

    sys.path.insert(0, str(REPO_ROOT))
    from runtime.redaction_evaluation.backends import CANDIDATE_IDS

    results = [measure(candidate_id, args.iterations) for candidate_id in CANDIDATE_IDS]
    document = {
        "schema_version": 1,
        "generated_by": "scripts/measure_redaction_memory.py",
        "candidates": results,
    }
    out_dir = REPO_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "memory-isolated.json"
    out_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"written {out_path}")
    for entry in results:
        peak = entry.get("peak_bytes")
        shown = f"{int(peak) / 1e6:.1f} MB" if isinstance(peak, int) else entry["status"]
        print(f"  {entry['candidate_id']}: {shown}")
    return 0 if all(entry["status"] == "ok" for entry in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
