# SPDX-License-Identifier: MIT
"""Fault-injection backends proving the harness fails closed for ANY candidate.

Each fault wraps a real candidate identity so the resulting hard-gate evidence
is attributable, but the wrapped candidate's detector is never reached: the
fault fires first, exactly as a broken real backend would.
"""

from __future__ import annotations

import time

from ..policy import RedactionPolicy
from ..seam import (
    BackendError,
    BackendFinding,
    BackendHealth,
    BackendIdentity,
    BackendInvalidConfiguration,
    BackendUnavailable,
)

FAULT_MODES = (
    "invalid_configuration",
    "missing_model",
    "init_failure",
    "exception",
    "hang",
    "worker_crash",
    "timeout_storm",
    "malformed_spans_out_of_range",
    "malformed_spans_overlapping",
    "nondeterministic",
)


class FaultInjectedBackend:
    """A backend that misbehaves in one pinned, typed way."""

    def __init__(self, base_identity: BackendIdentity, fault: str) -> None:
        if fault not in FAULT_MODES:
            raise ValueError(f"unknown_fault:{fault}")
        self._fault = fault
        self._calls = 0
        self._identity = BackendIdentity(
            candidate_id=base_identity.candidate_id,
            family=base_identity.family,
            engine_version=base_identity.engine_version,
            packages=base_identity.packages,
            models=base_identity.models,
            configuration={**base_identity.configuration, "injected_fault": fault},
        )

    @property
    def identity(self) -> BackendIdentity:
        return self._identity

    def initialize(self) -> None:
        if self._fault == "invalid_configuration":
            raise BackendInvalidConfiguration("backend_invalid_configuration")
        if self._fault == "missing_model":
            raise BackendUnavailable("backend_unavailable")
        if self._fault == "init_failure":
            raise BackendUnavailable("backend_unavailable")

    def health(self) -> BackendHealth:
        if self._fault in ("invalid_configuration", "missing_model", "init_failure"):
            return BackendHealth(ready=False, detail=self._fault)
        return BackendHealth(ready=True)

    def analyze(
        self,
        text: str,
        *,
        field_path: str,
        policy: RedactionPolicy,
    ) -> list[BackendFinding]:
        del field_path
        self._calls += 1
        if self._fault == "exception":
            raise RuntimeError("synthetic backend crash")
        if self._fault == "worker_crash":
            # Simulates an abrupt engine death rather than a typed error.
            raise BackendError("backend_crash")
        if self._fault in ("hang", "timeout_storm"):
            time.sleep(policy.per_record_budget_seconds + 30.0)
            return []
        if self._fault == "malformed_spans_out_of_range":
            return [
                BackendFinding(
                    category="pii",
                    subtype="person",
                    start=0,
                    end=len(text) + 50,
                    backend_label="broken",
                )
            ]
        if self._fault == "malformed_spans_overlapping":
            if len(text) < 4:
                return []
            return [
                BackendFinding("pii", "person", 3, 1, backend_label="inverted"),
                BackendFinding("pii", "person", 0, 2, backend_label="dup"),
            ]
        if self._fault == "nondeterministic":
            # Output depends on call count: repeated identical inputs diverge.
            if self._calls % 2 == 0 and len(text) >= 2:
                return [BackendFinding("pii", "person", 0, 1, backend_label="flip")]
            return []
        return []
