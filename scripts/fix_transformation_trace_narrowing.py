#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Apply the explicit phase narrowing required by mypy."""

from pathlib import Path

path = Path("runtime/transformation_trace.py")
text = path.read_text(encoding="utf-8")
old = '''    required = {
        "observation": observation_phase,
        "adapter_emission": emission_phase,
        "external_envelope": envelope_phase,
    }
    missing = [name for name, phase in required.items() if phase is None]
    if missing:
        raise TransformationTraceContractError(
            "missing_required_legacy_phases:" + ",".join(missing)
        )
'''
new = '''    missing: list[str] = []
    if observation_phase is None:
        missing.append("observation")
    if emission_phase is None:
        missing.append("adapter_emission")
    if envelope_phase is None:
        missing.append("external_envelope")
    if missing:
        raise TransformationTraceContractError(
            "missing_required_legacy_phases:" + ",".join(missing)
        )
    assert observation_phase is not None
    assert emission_phase is not None
    assert envelope_phase is not None
'''
if new in text:
    raise SystemExit(0)
if old not in text:
    raise SystemExit("expected narrowing block not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
