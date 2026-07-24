# SPDX-License-Identifier: MIT
"""CLI wrapper for hosted ADR-0020 evidence validation."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from runtime.redaction_evaluation.hosted_validation import (  # noqa: E402
    main,
    validate_repository,
)

__all__ = ["main", "validate_repository"]


if __name__ == "__main__":
    raise SystemExit(main())
