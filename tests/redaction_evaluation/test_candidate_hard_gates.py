# SPDX-License-Identifier: MIT
"""Harness self-tests for the ADR-0020 evaluation runner and metrics.

Runs without any heavy candidate dependency: only the baseline stdlib
backend, the fault-injection backends, and small fake backends composed at
runtime. No model loads, no corpus files required.

Secret-shaped strings are always composed from parts at runtime so no
secret-shaped literal is ever committed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.redaction_evaluation.backends.baseline import (  # noqa: E402
    BicameralStdlibBackend,
)
from runtime.redaction_evaluation.boundary import (  # noqa: E402
    RecordingCursor,
    RecordingSink,
    route_outcome,
)
from runtime.redaction_evaluation.metrics import (  # noqa: E402
    f_beta,
    finalize_bucket,
    match_findings,
    safe_ratio,
)
from runtime.redaction_evaluation.policy import RedactionPolicy  # noqa: E402
from runtime.redaction_evaluation.runner import (  # noqa: E402
    aggregate_gates,
    apply_replacements,
    process_record,
    resolve_overlaps,
    run_worker_timeout_storm,
)
from runtime.redaction_evaluation.seam import (  # noqa: E402
    BackendFinding,
    BackendHealth,
    BackendIdentity,
)
from runtime.redaction_evaluation.worker import (  # noqa: E402
    CandidateWorkerManager,
    WorkerFailure,
)

POLICY = RedactionPolicy()

# Composed at runtime; never a committed secret-shaped literal.
FAKE_AWS_KEY = "AKIA" + "EXAMPLE000000001"

STDLIB_ID = "bicameral-stdlib-v1"
TEST_CONFIG_DIGEST = "sha256:" + "0" * 64  # attribution placeholder for tests


@pytest.fixture(scope="module")
def stdlib_manager():
    manager = CandidateWorkerManager(STDLIB_ID, configuration_digest=TEST_CONFIG_DIGEST)
    manager.prewarm(60.0)
    yield manager
    manager.shutdown()


class NoopBackend:
    """A backend that finds nothing (used to prove the hard-screen backstop)."""

    def __init__(self) -> None:
        self._identity = BackendIdentity(
            candidate_id="noop-test-v1",
            family="test",
            engine_version="0.0.0",
            packages={"none": "0"},
        )

    @property
    def identity(self) -> BackendIdentity:
        return self._identity

    def initialize(self) -> None:
        return None

    def health(self) -> BackendHealth:
        return BackendHealth(ready=True)

    def analyze(
        self, text: str, *, field_path: str, policy: RedactionPolicy
    ) -> list[BackendFinding]:
        del text, field_path, policy
        return []


def make_record(
    *,
    record_id: str = "unit-record-001",
    excerpt: str = "plain text with no sensitive content",
    title: str = "unit title",
    author: str = "unit author",
    metadata: dict[str, Any] | None = None,
    evidence_metadata: dict[str, Any] | None = None,
    identity_overrides: dict[str, str] | None = None,
    eval_directives: dict[str, Any] | None = None,
) -> dict[str, Any]:
    observation: dict[str, Any] = {
        "source_ref": {
            "source_id": "unit-source",
            "ref": "unit-ref",
            "url": "https://example.invalid/unit",
            "kind": "synthetic",
        },
        "excerpt": excerpt,
        "title": title,
        "author": author,
        "mode": "batch",
        "timestamp": "2026-01-01T00:00:00Z",
        "provider_event_id": "unit-event-001",
        "provider_resource_id": "unit-resource-001",
        "evidence_id": "unit-evidence-001",
        "evidence_metadata": evidence_metadata or {},
        "metadata": metadata or {},
    }
    for key, value in (identity_overrides or {}).items():
        observation[key] = value
    record: dict[str, Any] = {
        "record_id": record_id,
        "source_shape": "observation",
        "observation": observation,
    }
    if eval_directives is not None:
        record["eval_directives"] = eval_directives
    return record


def run(record: dict[str, Any], backend: Any = None, policy: RedactionPolicy = POLICY):
    return process_record(
        record,
        backend=backend or BicameralStdlibBackend(),
        policy=policy,
        classes=("positive_detection",),
        determinism_repeats=2,
        fault_budget_seconds=0.5,
    )


def run_with_manager(
    record: dict[str, Any],
    manager: CandidateWorkerManager,
    policy: RedactionPolicy = POLICY,
):
    return process_record(
        record,
        backend=BicameralStdlibBackend(),
        policy=policy,
        classes=("positive_detection",),
        determinism_repeats=2,
        fault_budget_seconds=0.5,
        manager=manager,
    )


# ---------------------------------------------------------------------------
# Fault reasons map to expected typed failures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fault", "reason"),
    [
        ("invalid_configuration", "backend_invalid_configuration"),
        ("missing_model", "backend_unavailable"),
        ("init_failure", "backend_unavailable"),
        ("exception", "backend_crash"),
        ("malformed_spans_out_of_range", "malformed_backend_findings"),
        ("malformed_spans_overlapping", "malformed_backend_findings"),
    ],
)
def test_in_process_fault_reasons(fault: str, reason: str) -> None:
    outcome = run(make_record(eval_directives={"fault": fault}))
    assert outcome.result["outcome"] == "failed_closed"
    assert outcome.result["failure_reason"] == reason
    # Fail-closed results are value-free: no sanitized content or findings.
    assert "field_digests" not in outcome.result
    assert "findings" not in outcome.result


def test_validation_faults_record_their_scope() -> None:
    outcome = run(make_record(eval_directives={"fault": "exception"}))
    assert outcome.result["probe_scope"] == "finding_validation"


def test_nondeterministic_probe_detected() -> None:
    outcome = run(make_record(eval_directives={"fault": "nondeterministic"}))
    assert outcome.result["outcome"] == "failed_closed"
    assert outcome.result["failure_reason"] == "nondeterministic_backend_output"
    assert outcome.result["probe_scope"] == "finding_validation"


# ---------------------------------------------------------------------------
# Candidate worker execution (issue #290): enforced deadlines, real kills
# ---------------------------------------------------------------------------


def test_worker_execution_matches_in_process(stdlib_manager) -> None:
    stdlib_manager.prewarm(60.0)
    record = make_record(
        metadata={"webhook": {"issue": {"body": "reach me at a@example.com"}}}
    )
    via_worker = run_with_manager(record, stdlib_manager)
    in_process = run(record)
    for key in ("outcome", "findings", "field_digests", "identity_digests"):
        assert via_worker.result[key] == in_process.result[key]
    assert via_worker.result["repeat_digests"] == in_process.result["repeat_digests"]
    assert isinstance(via_worker.result["worker_pid"], int)


def test_hang_directive_enforces_termination_with_evidence(stdlib_manager) -> None:
    stdlib_manager.prewarm(60.0)
    pid_before = stdlib_manager.worker_pid()
    outcome = run_with_manager(
        make_record(eval_directives={"fault": "hang"}), stdlib_manager
    )
    result = outcome.result
    assert result["outcome"] == "failed_closed"
    assert result["failure_reason"] == "backend_timeout"
    cleanup = result["cleanup"]
    assert cleanup["candidate_id"] == STDLIB_ID
    assert cleanup["configuration_digest"] == TEST_CONFIG_DIGEST
    assert cleanup["outcome"] in ("terminated", "killed")
    assert cleanup["pid"] == pid_before
    # The hung worker is verifiably gone, not abandoned.
    assert stdlib_manager.worker_alive() is False


def test_worker_crash_directive_reports_backend_crash(stdlib_manager) -> None:
    stdlib_manager.prewarm(60.0)
    outcome = run_with_manager(
        make_record(eval_directives={"fault": "worker_crash"}), stdlib_manager
    )
    result = outcome.result
    assert result["outcome"] == "failed_closed"
    assert result["failure_reason"] == "backend_crash"
    assert result["cleanup"]["candidate_id"] == STDLIB_ID


def test_worker_timeout_storm_bounded_cleanup_and_recovery(stdlib_manager) -> None:
    pytest.importorskip("psutil")
    observation = make_record()["observation"]
    storm = run_worker_timeout_storm(
        observation, POLICY, 0.5, stdlib_manager, concurrency=3
    )
    assert storm["all_timed_out"] is True
    assert storm["orphans"] == 0
    assert storm["cleanup_ok"] is True
    assert storm["recovered"] is True
    assert storm["candidate_id"] == STDLIB_ID
    assert storm["worker_pids"]


def test_cold_worker_completes_inside_production_budget(stdlib_manager) -> None:
    # Production lazy-spawn semantics: initialization inside the 5 s budget.
    stdlib_manager.shutdown()
    doc = stdlib_manager.call(make_record()["observation"], POLICY, {}, 5.0)
    assert doc["outcome"] in ("sanitized", "unchanged")


def test_manager_call_raises_typed_worker_failure(stdlib_manager) -> None:
    stdlib_manager.prewarm(60.0)
    with pytest.raises(WorkerFailure) as excinfo:
        stdlib_manager.call(
            make_record()["observation"], POLICY, {"fault": "hang"}, 0.3
        )
    assert excinfo.value.reason == "backend_timeout"


def test_typed_failure_keeps_worker_alive(stdlib_manager) -> None:
    stdlib_manager.prewarm(60.0)
    record = make_record(metadata={"contact@example.com": "value"})
    outcome = run_with_manager(record, stdlib_manager)
    assert outcome.result["failure_reason"] == "sensitive_metadata_key"
    # A typed in-child rejection is not a crash: no recycle needed.
    assert stdlib_manager.worker_alive() is True


# ---------------------------------------------------------------------------
# Observed sink/cursor boundary (issue #290): calls, not modeled booleans
# ---------------------------------------------------------------------------


def test_failed_record_routes_nothing() -> None:
    sink = RecordingSink()
    cursor = RecordingCursor()
    route_outcome(
        {"record_id": "unit-fail", "outcome": "failed_closed"}, sink, cursor
    )
    assert sink.call_count == 0
    assert cursor.advance_count == 0


def test_sanitized_record_routes_exactly_once_and_value_free() -> None:
    sink = RecordingSink()
    cursor = RecordingCursor()
    route_outcome({"record_id": "unit-ok", "outcome": "sanitized"}, sink, cursor)
    assert sink.call_count == 1
    assert sink.emission_counts == [1]
    assert sink.routed_record_ids == ["unit-ok"]
    assert cursor.advance_count == 1
    assert cursor.advanced_record_ids == ["unit-ok"]


# ---------------------------------------------------------------------------
# Aggregate gate state: pending is never a pass
# ---------------------------------------------------------------------------


def test_pending_gate_yields_pending_not_passed() -> None:
    gates = [
        {"gate_id": "a", "status": "passed"},
        {"gate_id": "b", "status": "pending"},
    ]
    aggregate = aggregate_gates(gates)
    assert aggregate["aggregate_state"] == "pending"
    assert aggregate["passed"] is False
    assert aggregate["pending_gate_ids"] == ["b"]
    assert aggregate["failed_gate_ids"] == []


def test_failed_gate_dominates_aggregate() -> None:
    gates = [
        {"gate_id": "a", "status": "pending"},
        {"gate_id": "b", "status": "failed"},
        {"gate_id": "c", "status": "passed"},
    ]
    aggregate = aggregate_gates(gates)
    assert aggregate["aggregate_state"] == "failed"
    assert aggregate["passed"] is False
    assert aggregate["failed_gate_ids"] == ["b"]


def test_all_passed_aggregate() -> None:
    gates = [{"gate_id": "a", "status": "passed"}]
    aggregate = aggregate_gates(gates)
    assert aggregate["aggregate_state"] == "passed"
    assert aggregate["passed"] is True


# ---------------------------------------------------------------------------
# Overlap resolution and replacement
# ---------------------------------------------------------------------------


def test_overlap_resolution_deterministic_regardless_of_input_order() -> None:
    findings = [
        BackendFinding("pii", "phone", 10, 22),
        BackendFinding("pii", "email", 5, 15),
        BackendFinding("secret", "secret", 5, 25),
        BackendFinding("pii", "person", 30, 40),
    ]
    resolved_forward = resolve_overlaps(findings)
    resolved_reversed = resolve_overlaps(list(reversed(findings)))
    assert resolved_forward == resolved_reversed
    # (5, -20, "secret") sorts before (5, -10, "email"): longest-at-start wins;
    # the shorter overlapping spans are greedily skipped.
    assert [(f.start, f.end, f.subtype) for f in resolved_forward] == [
        (5, 25, "secret"),
        (30, 40, "person"),
    ]


def test_overlap_resolution_tie_breaks_on_subtype() -> None:
    findings = [
        BackendFinding("pii", "phone", 0, 4),
        BackendFinding("pii", "email", 0, 4),
    ]
    resolved = resolve_overlaps(findings)
    assert len(resolved) == 1
    assert resolved[0].subtype == "email"  # alphabetical tie-break


def test_replacement_right_to_left_multi_span() -> None:
    text = "call 111 or 222 now"
    findings = [
        BackendFinding("pii", "phone", 5, 8),
        BackendFinding("pii", "phone", 12, 15),
    ]
    out = apply_replacements(text, findings, POLICY)
    assert out == "call [redacted:phone] or [redacted:phone] now"


# ---------------------------------------------------------------------------
# Screens and guards
# ---------------------------------------------------------------------------


def test_post_screen_escape_recorded_cleanly() -> None:
    outcome = run(
        make_record(excerpt=f"deploy key {FAKE_AWS_KEY} in text"), backend=NoopBackend()
    )
    assert outcome.result["outcome"] == "failed_closed"
    assert outcome.result["failure_reason"] == "post_screen_escape"
    assert outcome.result["post_screen_hits"] >= 1
    # Fail-closed is value-free: no sanitized content anywhere. The
    # no-envelope/no-cursor invariant is OBSERVED via the boundary doubles.
    assert "field_digests" not in outcome.result
    assert FAKE_AWS_KEY not in str(outcome.result)
    sink = RecordingSink()
    cursor = RecordingCursor()
    route_outcome(outcome.result, sink, cursor)
    assert sink.call_count == 0
    assert cursor.advance_count == 0


def test_identity_screen_failure() -> None:
    outcome = run(
        make_record(identity_overrides={"provider_event_id": FAKE_AWS_KEY})
    )
    assert outcome.result["outcome"] == "failed_closed"
    assert outcome.result["failure_reason"] == "sensitive_identity_field"
    assert FAKE_AWS_KEY not in str(outcome.result)


def test_sensitive_metadata_key_rejected() -> None:
    outcome = run(make_record(metadata={"contact@example.com": "value"}))
    assert outcome.result["outcome"] == "failed_closed"
    assert outcome.result["failure_reason"] == "sensitive_metadata_key"


def test_oversized_payload_rejected() -> None:
    policy = RedactionPolicy(max_payload_bytes=256)
    outcome = run(make_record(excerpt="x" * 1024), policy=policy)
    assert outcome.result["outcome"] == "failed_closed"
    assert outcome.result["failure_reason"] == "oversized_payload"


def test_binary_field_rejected() -> None:
    outcome = run(
        make_record(
            metadata={"attachment": "placeholder"},
            eval_directives={
                "binary_field": {
                    "path": "metadata.attachment",
                    "base64": "AAECAwQ=",
                }
            },
        )
    )
    assert outcome.result["outcome"] == "failed_closed"
    assert outcome.result["failure_reason"] == "unsupported_binary"


def test_clean_record_unchanged_and_deterministic() -> None:
    outcome = run(make_record())
    assert outcome.result["outcome"] == "unchanged"
    digests = outcome.result["repeat_digests"]
    assert len(digests) == 2 and digests[0] == digests[1]
    assert outcome.result["identity_digests"]


def test_baseline_sanitizes_email_in_nested_metadata() -> None:
    outcome = run(
        make_record(
            metadata={"webhook": {"issue": {"body": "reach me at a@example.com"}}}
        )
    )
    assert outcome.result["outcome"] == "sanitized"
    paths = [f["field_path"] for f in outcome.result["findings"]]
    assert "metadata.webhook.issue.body" in paths
    assert (
        outcome.sanitized_fields["metadata.webhook.issue.body"]
        == "reach me at [redacted:email]"
    )


# ---------------------------------------------------------------------------
# Matching rules (metrics)
# ---------------------------------------------------------------------------


def _cand(start: int, end: int, category: str = "pii", subtype: str = "email") -> dict:
    return {
        "category": category,
        "subtype": subtype,
        "field_path": "excerpt",
        "start": start,
        "end": end,
    }


def _exp(
    entity_id: str,
    start: int,
    end: int,
    category: str = "pii",
    subtype: str = "email",
) -> dict:
    return {
        "entity_id": entity_id,
        "category": category,
        "subtype": subtype,
        "field_path": "excerpt",
        "start": start,
        "end": end,
    }


def test_matching_prefers_maximum_overlap() -> None:
    candidates = [_cand(0, 10), _cand(8, 20)]
    expected = [_exp("e1", 5, 20)]
    matches, fps, fns = match_findings(candidates, expected)
    assert len(matches) == 1 and not fns
    assert matches[0][0]["start"] == 8  # overlap 12 beats overlap 5
    assert fps == [candidates[0]]


def test_matching_overlap_tie_breaks_on_candidate_start() -> None:
    candidates = [_cand(4, 8), _cand(0, 4)]
    expected = [_exp("e1", 2, 6)]
    matches, fps, _fns = match_findings(candidates, expected)
    # Both overlap by 2; the lower candidate start wins deterministically.
    assert matches[0][0]["start"] == 0
    assert fps == [candidates[0]]


def test_matching_is_one_to_one() -> None:
    candidates = [_cand(0, 10)]
    expected = [_exp("e1", 0, 5), _exp("e2", 5, 10)]
    matches, fps, fns = match_findings(candidates, expected)
    assert len(matches) == 1
    assert not fps
    assert len(fns) == 1  # the second entity stays unmatched -> FN


def test_matching_requires_category_equality() -> None:
    candidates = [_cand(0, 10, category="secret", subtype="secret")]
    expected = [_exp("e1", 0, 10, category="pii", subtype="email")]
    matches, fps, fns = match_findings(candidates, expected)
    assert not matches and len(fps) == 1 and len(fns) == 1


def test_zero_denominator_emits_null_with_note() -> None:
    bucket = finalize_bucket({"tp": 0, "fp": 0, "fn": 0, "exact_span": 0})
    assert bucket["precision"] is None
    assert bucket["precision_note"] == "no_positive_predictions"
    assert bucket["recall"] is None
    assert bucket["recall_note"] == "no_expected_entities"
    assert bucket["f1"] is None
    assert bucket["f1_note"] == "undefined_precision_or_recall"
    assert bucket["f2"] is None


def test_precision_and_recall_zero_yields_null_f_scores() -> None:
    bucket = finalize_bucket({"tp": 0, "fp": 3, "fn": 2, "exact_span": 0})
    assert bucket["precision"] == 0.0
    assert bucket["recall"] == 0.0
    assert bucket["f1"] is None
    assert bucket["f1_note"] == "precision_and_recall_zero"


def test_f2_formula() -> None:
    precision, recall = 0.5, 1.0
    f2, note = f_beta(precision, recall, 4.0)
    assert note is None
    assert f2 == pytest.approx(5 * precision * recall / (4 * precision + recall))
    value, ratio_note = safe_ratio(3, 4, "unused")
    assert value == 0.75 and ratio_note is None
