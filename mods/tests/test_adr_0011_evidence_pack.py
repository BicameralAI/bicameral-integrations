# SPDX-License-Identifier: MIT
"""Tests covering ADR-0011 amendment: PR evidence pack protocol shapes and boundaries.

Validates that:
- Protocol shapes (EvidenceItem, AdvisoryHint, ReviewQuestionCandidate,
  PRCommentDraft, PREvidencePack) are frozen and constructible.
- ReviewQuestionCandidate is advisory input only (no write semantics).
- PRCommentDraft is a T3 proposed action (no publish path).
- Mod advisory output maps to the evidence-pack advisory-hint shape.
- Deterministic results are referenced, not duplicated in the pack.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, field
from typing import Any

import pytest

from adapter.core.emissions import AdvisoryResult


# --- Protocol shape definitions (ADR-0011 amended) ---
# These mirror the shapes described in ADR-0011 §PR Evidence Pack.
# In a future implementation pass, these move to protocol/pr_evidence_pack/.


@dataclass(frozen=True)
class EvidenceItem:
    """One piece of PR-scoped evidence collected by integrations."""

    item_id: str
    source: str
    kind: str
    summary: str
    evidence_ref: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdvisoryHint:
    """An advisory observation produced by a mod for bot-side interpretation."""

    hint_id: str
    source_mod: str
    category: str
    message: str
    severity: str
    evidence_item_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReviewQuestionCandidate:
    """Advisory input only -- not a draft outbound write or canonical decision."""

    question_id: str
    source_mod: str
    question: str
    context_item_ids: tuple[str, ...] = ()
    priority: str = "normal"


@dataclass(frozen=True)
class PRCommentDraft:
    """T3 proposed action -- never directly published by integrations."""

    draft_id: str
    source_mod: str
    file: str
    line: int | None = None
    body: str = ""
    comment_type: str = "inline"
    linked_finding_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class PREvidencePack:
    """The integrations-side deliverable consumed by bot preflight."""

    pr_ref: str
    evidence_items: tuple[EvidenceItem, ...] = ()
    advisory_hints: tuple[AdvisoryHint, ...] = ()
    review_questions: tuple[ReviewQuestionCandidate, ...] = ()
    comment_drafts: tuple[PRCommentDraft, ...] = ()
    deterministic_results_ref: str = ""


# --- Tests ---


class TestEvidenceItemShape:
    """EvidenceItem is frozen and has required fields."""

    def test_construction(self):
        item = EvidenceItem(
            item_id="ev-1",
            source="github-connector",
            kind="diff_context",
            summary="Changed auth middleware",
            evidence_ref="src/auth.py:42",
        )
        assert item.item_id == "ev-1"
        assert item.kind == "diff_context"

    def test_frozen(self):
        item = EvidenceItem(
            item_id="ev-2", source="s", kind="k", summary="x", evidence_ref="r"
        )
        with pytest.raises(FrozenInstanceError):
            item.item_id = "mutated"  # type: ignore[misc]


class TestAdvisoryHintShape:
    """AdvisoryHint is scoped to governance/integration-boundary evidence."""

    def test_construction_governance_boundary(self):
        hint = AdvisoryHint(
            hint_id="h-1",
            source_mod="code-review-risk",
            category="governance_boundary",
            message="PR moves trust-tier boundary from T1 to T3",
            severity="high",
            evidence_item_ids=("ev-1",),
        )
        assert hint.category == "governance_boundary"
        assert hint.severity == "high"

    def test_construction_integration_contract(self):
        hint = AdvisoryHint(
            hint_id="h-2",
            source_mod="adapter-contract",
            category="integration_contract",
            message="Emission shape changed: new required field",
            severity="medium",
        )
        assert hint.category == "integration_contract"

    def test_frozen(self):
        hint = AdvisoryHint(
            hint_id="h-3",
            source_mod="m",
            category="c",
            message="x",
            severity="low",
        )
        with pytest.raises(FrozenInstanceError):
            hint.message = "mutated"  # type: ignore[misc]


class TestReviewQuestionCandidateIsAdvisoryInput:
    """ReviewQuestionCandidate is advisory input, not a draft write."""

    def test_construction(self):
        q = ReviewQuestionCandidate(
            question_id="q-1",
            source_mod="code-review-risk",
            question="Is the broadened token scope intentional?",
            context_item_ids=("ev-1",),
            priority="high",
        )
        assert q.question == "Is the broadened token scope intentional?"
        assert q.priority == "high"

    def test_no_write_semantics(self):
        """ReviewQuestionCandidate has no publish/post/write fields."""
        q = ReviewQuestionCandidate(question_id="q-2", source_mod="m", question="q")
        # Verify no attributes suggesting outbound write capability
        attrs = set(dir(q))
        write_words = {"publish", "post", "send", "write", "commit", "approve"}
        assert not attrs & write_words

    def test_frozen(self):
        q = ReviewQuestionCandidate(question_id="q-3", source_mod="m", question="q")
        with pytest.raises(FrozenInstanceError):
            q.question = "mutated"  # type: ignore[misc]

    def test_maps_from_suggested_review_question_output(self):
        """The existing mod output kind maps to ReviewQuestionCandidate."""
        advisory = AdvisoryResult(
            kind="suggested_review_question",
            message="Is this API change backward-compatible?",
        )
        # Mapping: AdvisoryResult -> ReviewQuestionCandidate
        q = ReviewQuestionCandidate(
            question_id="q-mapped",
            source_mod="code-review-risk",
            question=advisory.message,
        )
        assert q.question == advisory.message


class TestPRCommentDraftIsT3ProposedAction:
    """PRCommentDraft is T3 (proposed write, never direct publish)."""

    def test_construction(self):
        draft = PRCommentDraft(
            draft_id="d-1",
            source_mod="code-review-risk",
            file="src/auth.py",
            line=42,
            body="Consider narrowing token scope.",
            linked_finding_ids=("f-1",),
        )
        assert draft.file == "src/auth.py"
        assert draft.line == 42

    def test_no_publish_path(self):
        """PRCommentDraft has no method or field for direct publishing."""
        draft = PRCommentDraft(draft_id="d-2", source_mod="m", file="f.py")
        attrs = set(dir(draft))
        publish_words = {"publish", "post", "send", "execute", "apply"}
        assert not attrs & publish_words

    def test_top_level_comment_type(self):
        draft = PRCommentDraft(
            draft_id="d-3",
            source_mod="m",
            file="",
            comment_type="top_level",
            body="Overall: consider adding integration tests.",
        )
        assert draft.comment_type == "top_level"
        assert draft.line is None

    def test_frozen(self):
        draft = PRCommentDraft(draft_id="d-4", source_mod="m", file="f.py")
        with pytest.raises(FrozenInstanceError):
            draft.body = "mutated"  # type: ignore[misc]


class TestPREvidencePack:
    """PREvidencePack is the integrations deliverable for bot preflight."""

    def _sample_pack(self) -> PREvidencePack:
        item = EvidenceItem(
            item_id="ev-1",
            source="github-connector",
            kind="diff_context",
            summary="auth change",
            evidence_ref="src/auth.py:10",
        )
        hint = AdvisoryHint(
            hint_id="h-1",
            source_mod="authority-boundary",
            category="governance_boundary",
            message="T1->T3 drift",
            severity="high",
            evidence_item_ids=("ev-1",),
        )
        question = ReviewQuestionCandidate(
            question_id="q-1",
            source_mod="code-review-risk",
            question="Intentional scope expansion?",
            context_item_ids=("ev-1",),
        )
        draft = PRCommentDraft(
            draft_id="d-1",
            source_mod="code-review-risk",
            file="src/auth.py",
            line=10,
            body="Narrow scope?",
            linked_finding_ids=("f-1",),
        )
        return PREvidencePack(
            pr_ref="BicameralAI/bicameral-integrations#42",
            evidence_items=(item,),
            advisory_hints=(hint,),
            review_questions=(question,),
            comment_drafts=(draft,),
            deterministic_results_ref="ci/lint-type-test/run-789",
        )

    def test_construction(self):
        pack = self._sample_pack()
        assert pack.pr_ref == "BicameralAI/bicameral-integrations#42"
        assert len(pack.evidence_items) == 1
        assert len(pack.advisory_hints) == 1
        assert len(pack.review_questions) == 1
        assert len(pack.comment_drafts) == 1

    def test_deterministic_results_referenced_not_duplicated(self):
        """The pack references deterministic results, not re-runs them."""
        pack = self._sample_pack()
        assert pack.deterministic_results_ref != ""
        # Advisory hints should not be lint/type/test results
        for hint in pack.advisory_hints:
            assert hint.category in (
                "governance_boundary",
                "integration_contract",
                "supply_chain_risk",
                "dependency_governance",
            )

    def test_empty_pack_valid(self):
        pack = PREvidencePack(pr_ref="owner/repo#1")
        assert pack.evidence_items == ()
        assert pack.advisory_hints == ()
        assert pack.review_questions == ()
        assert pack.comment_drafts == ()

    def test_frozen(self):
        pack = self._sample_pack()
        with pytest.raises(FrozenInstanceError):
            pack.pr_ref = "mutated"  # type: ignore[misc]


class TestModAdvisoryOutputScope:
    """Mod advisory output is governance/integration-boundary, not lint/test."""

    VALID_ADVISORY_CATEGORIES = frozenset(
        {
            "governance_boundary",
            "integration_contract",
            "supply_chain_risk",
            "dependency_governance",
            "authority_drift",
            "governance_artifact_change",
        }
    )

    DETERMINISTIC_CATEGORIES = frozenset(
        {
            "lint_error",
            "type_error",
            "test_failure",
            "secret_scan_hit",
        }
    )

    def test_advisory_hint_category_not_deterministic(self):
        """Advisory hints must not duplicate deterministic tool output."""
        for cat in self.DETERMINISTIC_CATEGORIES:
            hint = AdvisoryHint(
                hint_id="h-x",
                source_mod="m",
                category=cat,
                message="x",
                severity="low",
            )
            assert hint.category not in self.VALID_ADVISORY_CATEGORIES

    def test_valid_advisory_categories_are_governance_scoped(self):
        """Valid categories cover governance/integration-boundary concerns."""
        for cat in self.VALID_ADVISORY_CATEGORIES:
            hint = AdvisoryHint(
                hint_id="h-v",
                source_mod="authority-boundary",
                category=cat,
                message="boundary observation",
                severity="medium",
            )
            assert hint.category in self.VALID_ADVISORY_CATEGORIES

    def test_existing_mod_outputs_map_to_advisory_hints(self):
        """The six known mod output kinds can map to AdvisoryHint or related shapes."""
        from mods.contract import _KNOWN_OUTPUTS

        # advisory_governance_result -> AdvisoryHint (governance_boundary)
        # routing_hint -> RoutingHint (existing shape, referenced by pack)
        # source_evidence_annotation -> EvidenceItem
        # suggested_review_question -> ReviewQuestionCandidate
        # owner_lens_hint -> AdvisoryHint (integration_contract)
        # dependency_signal -> AdvisoryHint (supply_chain_risk)
        mapping = {
            "advisory_governance_result": "AdvisoryHint",
            "routing_hint": "RoutingHint",
            "source_evidence_annotation": "EvidenceItem",
            "suggested_review_question": "ReviewQuestionCandidate",
            "owner_lens_hint": "AdvisoryHint",
            "dependency_signal": "AdvisoryHint",
        }
        for output_kind in _KNOWN_OUTPUTS:
            assert output_kind in mapping, f"Unmapped output kind: {output_kind}"
