# SPDX-License-Identifier: MIT
"""CLI wrapper for hosted ADR-0020 evidence validation."""

from runtime.redaction_evaluation.hosted_validation import main, validate_repository

__all__ = ["main", "validate_repository"]


if __name__ == "__main__":
    raise SystemExit(main())
