# SPDX-License-Identifier: MIT
"""Behavioral tests for the license-header checker."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_license_headers import missing_header, scan  # noqa: E402


def test_missing_header_true_when_absent():
    assert missing_header("connectors/x/connector.py", "import os\n\nx = 1\n") is True


def test_missing_header_false_when_present():
    assert missing_header("x.py", "# SPDX-License-Identifier: MIT\nimport os\n") is False


def test_empty_init_exempt():
    assert missing_header("connectors/x/__init__.py", "") is False


def test_non_python_exempt():
    assert missing_header("README.md", "no header here") is False


def test_scan_reports_only_missing(tmp_path):
    good = tmp_path / "good.py"
    good.write_text("# SPDX-License-Identifier: MIT\nx = 1\n", encoding="utf-8")
    bad = tmp_path / "bad.py"
    bad.write_text("x = 1\n", encoding="utf-8")
    result = scan([good, bad])
    assert str(bad) in result
    assert str(good) not in result
