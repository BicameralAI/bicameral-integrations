# SPDX-License-Identifier: MIT
"""Bicameral-owned evaluation policy: admitted fields, identity fields,
neutral categories, deterministic replacement, and configuration digesting.

The policy is identical for every candidate. It re-states, for the spike
harness, the same boundaries the production wrapper enforces in
``adapter.core.redaction_receipt``: which observation fields are sanitized,
which identity fields must stay byte-for-byte stable, and what the
deterministic replacement token looks like.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

NEUTRAL_CATEGORIES = ("secret", "credential", "pii", "phi", "prohibited_content")

ADMITTED_TEXT_FIELDS = ("excerpt", "title", "author")
ADMITTED_TREE_FIELDS = ("evidence_metadata", "metadata")
IDENTITY_FIELDS = (
    "source_ref.source_id",
    "source_ref.ref",
    "source_ref.url",
    "source_ref.kind",
    "provider_event_id",
    "provider_resource_id",
    "evidence_id",
    "timestamp",
)


@dataclass(frozen=True)
class RedactionPolicy:
    """Candidate-neutral policy handed to every backend and to the harness."""

    policy_id: str = "bicameral-eval-policy-v1"
    admitted_text_fields: tuple[str, ...] = ADMITTED_TEXT_FIELDS
    admitted_tree_fields: tuple[str, ...] = ADMITTED_TREE_FIELDS
    identity_fields: tuple[str, ...] = IDENTITY_FIELDS
    categories: tuple[str, ...] = NEUTRAL_CATEGORIES
    replacement_template: str = "[redacted:{subtype}]"
    overlap_rule: str = "max-overlap-greedy-1to1"
    per_record_budget_seconds: float = 20.0
    max_payload_bytes: int = 1_048_576

    def replacement(self, subtype: str) -> str:
        return self.replacement_template.format(subtype=subtype)

    def manifest(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "admitted_text_fields": list(self.admitted_text_fields),
            "admitted_tree_fields": list(self.admitted_tree_fields),
            "identity_fields": list(self.identity_fields),
            "categories": list(self.categories),
            "replacement_template": self.replacement_template,
            "overlap_rule": self.overlap_rule,
            "per_record_budget_seconds": self.per_record_budget_seconds,
            "max_payload_bytes": self.max_payload_bytes,
        }


@dataclass(frozen=True)
class LabelMap:
    """Versioned mapping from backend-native labels to neutral categories.

    ``mapping`` maps a backend label to ``(category, subtype)``. Labels absent
    from the map are dropped and counted as unmapped diagnostics rather than
    silently invented. The map participates in the candidate configuration
    digest, per the evaluation contract.
    """

    map_id: str
    mapping: dict[str, tuple[str, str]] = field(default_factory=dict)

    def manifest(self) -> dict[str, object]:
        return {
            "map_id": self.map_id,
            "mapping": {
                label: {"category": category, "subtype": subtype}
                for label, (category, subtype) in sorted(self.mapping.items())
            },
        }


def canonical_digest(value: object) -> str:
    """Deterministic ``sha256:`` digest of a JSON-serializable value."""

    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def configuration_digest(
    identity_configuration: dict[str, object],
    label_map: LabelMap,
    policy: RedactionPolicy,
) -> str:
    """Digest over the complete candidate configuration domain."""

    return canonical_digest(
        {
            "configuration": identity_configuration,
            "label_map": label_map.manifest(),
            "policy": policy.manifest(),
        }
    )
