# SPDX-License-Identifier: MIT
"""Smoke-run one candidate backend against three built-in synthetic samples.

Usage (from the repo root, inside the spike environment)::

    python -m runtime.redaction_evaluation.backends.smoke <candidate-id>

Prints each finding as a ``(category, subtype, start, end, backend_label)``
tuple plus the backend's unmapped-label counts. All sample values are
synthetic; the secret-shaped token is composed at runtime from parts so no
token-shaped literal is committed to the repository.
"""

from __future__ import annotations

import argparse

from ..policy import RedactionPolicy
from . import CANDIDATE_IDS, create_backend


def _samples() -> tuple[str, ...]:
    secret_shaped = "AKIA" + "EXAMPLE000000001"
    return (
        "Contact Avery Winslow at avery.winslow@example.com or +1 202 555 0143.",
        "Deploy key " + secret_shaped + " was rotated after the incident.",
        "Card 4111111111111111 MRN: 84920137",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one candidate backend over the synthetic smoke samples."
    )
    parser.add_argument("candidate_id", choices=CANDIDATE_IDS)
    args = parser.parse_args()

    backend = create_backend(args.candidate_id)
    backend.initialize()
    policy = RedactionPolicy()

    print(f"candidate: {backend.identity.candidate_id}")
    print(f"health: {backend.health()}")
    for index, sample in enumerate(_samples(), start=1):
        findings = backend.analyze(
            sample, field_path=f"smoke.sample_{index}", policy=policy
        )
        print(f"sample {index}: {sample!r}")
        if not findings:
            print("  (no findings)")
        for finding in findings:
            print(
                "  ("
                f"{finding.category!r}, {finding.subtype!r}, "
                f"{finding.start}, {finding.end}, {finding.backend_label!r})"
            )
    unmapped = getattr(backend, "unmapped_labels", None)
    print(f"unmapped labels: {unmapped() if callable(unmapped) else {}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
