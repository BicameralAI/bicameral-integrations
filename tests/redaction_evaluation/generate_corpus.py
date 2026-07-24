# SPDX-License-Identifier: MIT
"""Deterministic generator for the candidate-neutral redaction evaluation corpus.

Running this module twice produces byte-identical output: no timestamps, no
randomness, fully literal synthetic content. Every value in the corpus is
fabricated (documentation IP ranges, ``example.com`` mailboxes, 555-01xx
phone numbers, standard payment-card test numbers, invented names).

Secret-shaped synthetic tokens are assembled from split literals below so the
raw shape never appears in this file's bytes, and every committed corpus file
is scanned with the repository's own sensitive-data catalog before the
generator exits. Fields whose plain text would trip that catalog are
committed behind the ``__b64rev__`` obfuscation marker documented in
``corpus_loader``.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parents[1]
CORPUS_DIR = BASE / "corpus"
EXPECTED_DIR = BASE / "expected"
MANIFEST_PATH = BASE / "corpus-manifest.json"

CORPUS_ID = "bicameral-redaction-evaluation-v1"
CORPUS_DESCRIPTION = (
    "Synthetic candidate-neutral redaction evaluation corpus for the "
    "Bicameral boundary. Every value is fabricated; secret-shaped tokens are "
    "committed behind reversible byte-level obfuscation so no raw sensitive "
    "shape exists in repository bytes."
)

REL_CORPUS = "tests/redaction_evaluation/corpus"
REL_EXPECTED = "tests/redaction_evaluation/expected"

FIELD_PATH_MAX = 256


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SENSITIVE = _load_module(
    "_corpus_gen_sensitive", REPO_ROOT / "adapter" / "core" / "sensitive.py"
)
_LOADER = _load_module("_corpus_gen_loader", BASE / "corpus_loader.py")

detect_sensitive = _SENSITIVE.detect_sensitive


def _j(*parts: str) -> str:
    """Join split literals; keeps secret shapes out of this file's bytes."""
    return "".join(parts)


# --- synthetic sensitive constants (assembled, never literal) -----------------

AWS_KEY = _j("AK", "IA", "EXAMPLE000000001")
GITHUB_PAT = _j("gh", "p_", "ExampleExampleExampleExample0000000t")
GITHUB_FG_PAT = _j("github", "_pat_", "Example0" * 10, "0T")
JWT_TOKEN = _j(
    "ey", "JhbGciOiJIUzI1NiJ9", ".", "ey", "JzdWIiOiJzeW50aGV0aWMifQ", ".", "c2lnbmF0dXJl"
)
SLACK_TOKEN = _j("xo", "xb-", "000000000000-synthetic0token")
GOOGLE_KEY = _j("AI", "za", "SyntheticExampleValue00000000000000")
STRIPE_KEY = _j("sk", "_live_", "SyntheticExample000000000000")
OPENAI_KEY = _j("sk", "-", "SyntheticExampleSyntheticExample0000")
NPM_TOKEN = _j("np", "m_", "ExampleExampleExampleExample0000000n")
GITLAB_TOKEN = _j("gl", "pat-", "Example0Example00000")
AZURE_KEY = _j(
    "DefaultEndpoints",
    "Protocol=https;AccountName=synthstore;",
    "AccountKey=",
    "Example0" * 5,
    ";",
)
PEM_BLOCK = _j(
    "-----BEGIN RSA ",
    "PRIVATE KEY-----",
    "\nMIIBOgIBAAJBALSynthetic0ExampleBody\n",
    "-----END RSA ",
    "PRIVATE KEY-----",
)

PAN_VISA = _j("4111", "1111", "1111", "1111")
PAN_MC = _j("5555", "5555", "5555", "4444")
PAN_AMEX = _j("3782", "8224", "6310", "005")
IBAN_TEST = "GB82 WEST 1234 5698 7654 32"

MRN_TEXT = _j("MR", "N: ", "84920137")
PATIENT_LABEL = _j("patient", "_id: ", "449021")
SSN_LABEL = _j("ss", "n: ", "987-65-4321")
PHI_KEY_TEXT = _j("patient", "_id=449021")


# --- composition model --------------------------------------------------------


@dataclass(frozen=True)
class Ent:
    """One expected entity inside a composed text field."""

    text: str
    category: str
    subtype: str
    mandatory: bool = False


@dataclass(frozen=True)
class RecordSpec:
    record_id: str
    source_shape: str
    classes: tuple[str, ...]
    observation: dict[str, Any]
    outcome: str = "sanitized"
    failure_reason: str | None = None
    preserve: tuple[tuple[str, str], ...] = ()
    protect: tuple[str, ...] = ()
    directives: dict[str, Any] | None = None


PROTECT_IDENTITY: tuple[str, ...] = (
    "source_ref.source_id",
    "source_ref.ref",
    "provider_event_id",
    "provider_resource_id",
    "evidence_id",
    "timestamp",
)


def obs(
    *,
    excerpt: Any = "",
    title: Any = "",
    author: Any = "",
    source_id: str = "synthetic-notes",
    ref: str = "",
    url: str = "",
    kind: str = "note",
    timestamp: str = "2026-07-01T12:00:00Z",
    provider_event_id: str = "",
    provider_resource_id: str = "",
    evidence_id: str = "",
    evidence_metadata: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Observation template mirroring adapter/core/observations.Observation."""
    return {
        "source_ref": {"source_id": source_id, "ref": ref, "url": url, "kind": kind},
        "excerpt": excerpt,
        "title": title,
        "author": author,
        "mode": "active",
        "timestamp": timestamp,
        "provider_event_id": provider_event_id,
        "provider_resource_id": provider_resource_id,
        "evidence_id": evidence_id,
        "evidence_metadata": evidence_metadata if evidence_metadata is not None else {},
        "metadata": metadata if metadata is not None else {},
    }


@dataclass
class FlattenResult:
    plain: Any = None
    entities: list[tuple[str, int, int, Ent]] = field(default_factory=list)


def _flatten(node: Any, path: str, out: FlattenResult) -> Any:
    """Resolve composed tuples into plain strings, recording entity spans."""
    if isinstance(node, tuple):
        parts: list[str] = []
        pos = 0
        for part in node:
            if isinstance(part, Ent):
                out.entities.append((path, pos, pos + len(part.text), part))
                parts.append(part.text)
                pos += len(part.text)
            else:
                if not isinstance(part, str):
                    raise TypeError(f"composed part must be str or Ent at {path}")
                parts.append(part)
                pos += len(part)
        return "".join(parts)
    if isinstance(node, dict):
        return {
            key: _flatten(value, f"{path}.{key}" if path else key, out)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_flatten(item, f"{path}[{index}]", out) for index, item in enumerate(node)]
    return node


def _obfuscate_committed(node: Any) -> Any:
    """Wrap any string the sensitive catalog would flag in a __b64rev__ marker."""
    if isinstance(node, str):
        if detect_sensitive(node):
            return {"__b64rev__": _b64rev_text(node)}
        return node
    if isinstance(node, dict):
        return {key: _obfuscate_committed(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_obfuscate_committed(item) for item in node]
    return node


def _b64rev_text(text: str) -> str:
    return base64.b64encode(text[::-1].encode("utf-8")).decode("ascii")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _obfuscated_object_directive(path: str, value: dict[str, Any]) -> dict[str, Any]:
    canonical = _canonical_json(value)
    if not detect_sensitive(canonical):
        raise AssertionError("obfuscated_object fixture must trip the catalog")
    encoded = _b64rev_text(canonical)
    if detect_sensitive(encoded):
        raise AssertionError("encoded obfuscated_object payload trips the catalog")
    return {"obfuscated_object": {"path": path, "b64rev": encoded}}


# --- record inventory ---------------------------------------------------------


def build_records() -> list[RecordSpec]:
    records: list[RecordSpec] = []

    def add(
        record_id: str,
        source_shape: str,
        classes: tuple[str, ...],
        observation: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        records.append(
            RecordSpec(record_id, source_shape, classes, observation, **kwargs)
        )

    pii = "pii"
    pos = ("positive_detection",)

    # -- A. positive detection ------------------------------------------------
    add(
        "person-plain-001",
        "plain_text",
        pos,
        obs(
            excerpt=(
                Ent("Avery Winslow", pii, "person"),
                " will present the rollout summary.",
            )
        ),
    )
    add(
        "person-title-002",
        "plain_text",
        pos,
        obs(
            title=(Ent("Rowan Ellery", pii, "person"), " handoff notes"),
            excerpt=("Prepared with input from ", Ent("Marlowe Quist", pii, "person"), "."),
        ),
    )
    add(
        "person-multi-003",
        "plain_text",
        pos,
        obs(
            excerpt=(
                Ent("Avery Winslow", pii, "person"),
                " and ",
                Ent("Rowan Ellery", pii, "person"),
                " co-own the incident runbook.",
            )
        ),
    )
    add(
        "email-plain-001",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "Contact the maintainer at ",
                Ent("avery.winslow@example.com", pii, "email"),
                " for onboarding.",
            )
        ),
    )
    add(
        "email-subaddress-002",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "Weekly reports go to ",
                Ent("rowan.ellery+alerts@example.org", pii, "email"),
                " each Monday.",
            )
        ),
    )
    add(
        "email-with-name-003",
        "plain_text",
        pos,
        obs(
            excerpt=(
                Ent("Avery Winslow", pii, "person"),
                " <",
                Ent("avery.winslow@example.com", pii, "email"),
                "> signed off on the draft.",
            )
        ),
    )
    add(
        "phone-nanp-001",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "Call the pilot desk at ",
                Ent("+1 202 555 0143", pii, "phone"),
                " before noon.",
            )
        ),
    )
    add(
        "phone-intl-plus-002",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The London office is reachable at ",
                Ent("+44 20 7946 0912", pii, "phone"),
                " on weekdays.",
            )
        ),
    )
    add(
        "phone-intl-00-003",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The Berlin liaison dials ",
                Ent("0049 30 1234 5678", pii, "phone"),
                " for escalations.",
            )
        ),
    )
    add(
        "phone-keyword-004",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "Support line tel: ",
                Ent("020 7946 0958", pii, "phone"),
                " opens at nine.",
            )
        ),
    )
    add(
        "address-street-001",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "Ship the starter kit to ",
                Ent("14 Larkspur Court, Fable City, OR 97401", pii, "address"),
                " by Friday.",
            )
        ),
    )
    add(
        "address-postal-002",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "Mail is forwarded to ",
                Ent("82 Quill Hollow Road, Ashvale, VT 05901", pii, "address"),
                " during the pilot.",
            )
        ),
    )
    add(
        "address-billing-003",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The billing contact lists ",
                Ent("7 Bellwether Lane, Port Amaranth, CA 90089", pii, "address"),
                " on file.",
            )
        ),
    )
    add(
        "dob-prose-001",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The attendee born ",
                Ent("12 March 1988", pii, "dob"),
                " requested dietary notes.",
            )
        ),
    )
    add(
        "dob-prose-002",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "Her date of birth, ",
                Ent("1990-04-17", pii, "dob"),
                ", appears on the intake form.",
            )
        ),
    )
    add(
        "govid-ssn-labeled-001",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "Verify enrollment ",
                Ent(SSN_LABEL, "phi", "ssn_label", True),
                " before filing.",
            )
        ),
    )
    add(
        "govid-ssn-unlabeled-002",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The application shows ",
                Ent("987-65-4329", pii, "government_id"),
                " in the identity box.",
            )
        ),
    )
    add(
        "govid-passport-003",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The traveler presented passport ",
                Ent("K1234567", pii, "government_id"),
                " at check-in.",
            )
        ),
    )
    add(
        "financial-pan-visa-001",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "A test checkout used ",
                Ent(PAN_VISA, "credential", "pan", True),
                " on the sandbox gateway.",
            )
        ),
    )
    add(
        "financial-pan-amex-002",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The legacy fixture card ",
                Ent(PAN_AMEX, "credential", "pan", True),
                " remains in the seed data.",
            )
        ),
    )
    add(
        "financial-iban-003",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The refund was routed to ",
                Ent(IBAN_TEST, pii, "financial_id"),
                " last quarter.",
            )
        ),
    )
    add(
        "secret-aws-github-001",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The rotation drill found ",
                Ent(AWS_KEY, "secret", "aws-access-key", True),
                " and ",
                Ent(GITHUB_PAT, "secret", "github-pat", True),
                " in a sandbox log.",
            )
        ),
    )
    add(
        "secret-jwt-002",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The session capture replayed ",
                Ent(JWT_TOKEN, "secret", "jwt", True),
                " during the drill.",
            )
        ),
    )
    add(
        "secret-slack-google-003",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "Cleanup removed ",
                Ent(SLACK_TOKEN, "secret", "slack-token", True),
                " and ",
                Ent(GOOGLE_KEY, "secret", "google-api-key", True),
                " from the fixture.",
            )
        ),
    )
    add(
        "secret-stripe-pem-004",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The vault export held ",
                Ent(STRIPE_KEY, "secret", "stripe-live-key", True),
                " next to a key block ",
                Ent(PEM_BLOCK, "secret", "pem-private-key", True),
                " in plain text.",
            )
        ),
    )
    add(
        "secret-github-fine-grained-005",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The audit flagged ",
                Ent(GITHUB_FG_PAT, "secret", "github-fine-grained-pat", True),
                " before rotation.",
            )
        ),
    )
    add(
        "secret-openai-npm-006",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The build log leaked ",
                Ent(OPENAI_KEY, "secret", "openai-key", True),
                " and ",
                Ent(NPM_TOKEN, "secret", "npm-token", True),
                " during publish.",
            )
        ),
    )
    add(
        "phi-mrn-001",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The chart pull for ",
                Ent(MRN_TEXT, "phi", "mrn", True),
                " completed overnight.",
            )
        ),
    )
    add(
        "phi-patient-id-002",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The export row contained ",
                Ent(PATIENT_LABEL, "phi", "patient_id", True),
                " before scrubbing.",
            )
        ),
    )
    add(
        "account-id-001",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "Customer account ",
                Ent("88012345", pii, "account_id"),
                " was flagged for review.",
            )
        ),
    )
    add(
        "account-id-002",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The workspace account ",
                Ent("acct-podcast-9921", pii, "account_id"),
                " was renamed.",
            )
        ),
    )
    add(
        "ip-v4-001",
        "plain_text",
        pos,
        obs(excerpt=("The probe reports ", Ent("192.0.2.44", pii, "ip"), " unreachable.")),
    )
    add(
        "ip-v6-002",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "The gateway listens on ",
                Ent("2001:db8::7f", pii, "ip"),
                " for the pilot.",
            )
        ),
    )
    add(
        "ip-both-003",
        "plain_text",
        pos,
        obs(
            excerpt=(
                "Traffic moved from ",
                Ent("192.0.2.9", pii, "ip"),
                " to ",
                Ent("2001:db8::15", pii, "ip"),
                " overnight.",
            )
        ),
    )
    add(
        "mixed-entities-001",
        "plain_text",
        ("positive_detection", "mixed_entities"),
        obs(
            excerpt=(
                Ent("Dana Frost", pii, "person"),
                " can be reached at ",
                Ent("dana.frost@example.org", pii, "email"),
                " or ",
                Ent("+1 202 555 0158", pii, "phone"),
                " from ",
                Ent("192.0.2.77", pii, "ip"),
                ".",
            )
        ),
    )
    add(
        "mixed-entities-002",
        "plain_text",
        ("positive_detection", "mixed_entities"),
        obs(
            title=("Escalation for ", Ent("Sable Norwick", pii, "person")),
            excerpt=(
                "Deliveries pause at ",
                Ent("82 Quill Hollow Road, Ashvale, VT 05901", pii, "address"),
                " while account ",
                Ent("55103377", pii, "account_id"),
                " is audited.",
            ),
        ),
    )
    add(
        "mixed-entities-003",
        "plain_text",
        ("positive_detection", "mixed_entities"),
        obs(
            excerpt=(
                "The scan surfaced ",
                Ent(GITLAB_TOKEN, "secret", "gitlab-pat", True),
                " beside a note for ",
                Ent("Juniper Hale", pii, "person"),
                ".",
            )
        ),
    )
    add(
        "overlap-email-person-001",
        "plain_text",
        ("positive_detection", "overlapping_entities"),
        obs(
            excerpt=(
                "Ping ",
                Ent("rowan.ellery@example.org", pii, "email"),
                " when the export completes.",
            )
        ),
    )
    add(
        "overlap-name-phone-002",
        "plain_text",
        ("positive_detection", "overlapping_entities"),
        obs(
            excerpt=(
                "Reach ",
                Ent("Rowan Ellery", pii, "person"),
                "(",
                Ent("+1 202 555 0164", pii, "phone"),
                ") before Friday.",
            )
        ),
    )
    add(
        "nested-meta-001",
        "observation",
        ("positive_detection", "nested_metadata"),
        obs(
            excerpt="The sync completed without retries.",
            metadata={
                "contact": {
                    "note": (
                        "Escalate to ",
                        Ent("Avery Winslow", pii, "person"),
                        " at ",
                        Ent("avery.winslow@example.com", pii, "email"),
                        ".",
                    ),
                    "channel": "ops",
                }
            },
        ),
    )
    add(
        "nested-meta-002",
        "observation",
        ("positive_detection", "nested_metadata"),
        obs(
            excerpt="Evidence archived for the weekly report.",
            evidence_metadata={
                "note": (
                    "Reviewer callback ",
                    Ent("+1 202 555 0129", pii, "phone"),
                    " recorded.",
                )
            },
        ),
    )
    add(
        "nested-meta-003",
        "observation",
        ("positive_detection", "nested_metadata"),
        obs(
            excerpt="Thread imported with two comments.",
            metadata={
                "comments": [
                    {"body": ("Handoff owner is ", Ent("Marlowe Quist", pii, "person"), ".")},
                    {"body": "No blockers reported."},
                ]
            },
        ),
    )

    # -- B. Bicameral source and wire shapes ----------------------------------
    shape_classes = ("positive_detection", "structural_identity", "nested_metadata")
    obs_shape_classes = ("positive_detection", "structural_identity")

    add(
        "shape-github-webhook-issue-001",
        "github_webhook",
        shape_classes,
        obs(
            excerpt=(
                "Issue opened by ",
                Ent("Avery Winslow", pii, "person"),
                " requesting a contact update.",
            ),
            title="Contact update request",
            author="avery-winslow-sx",
            source_id="github",
            ref="issues/482",
            url="https://github.com/example-org/sample-service/issues/482",
            kind="issue",
            timestamp="2026-06-18T09:15:00Z",
            provider_event_id="9f2a6c1e-8d43-4a7b-9c0d-1e2f3a4b5c6d",
            provider_resource_id="I_kwDOExample482",
            evidence_id="ev-gh-issue-482",
            metadata={
                "webhook": {
                    "action": "opened",
                    "issue": {
                        "number": 482,
                        "title": ("Contact update for ", Ent("Avery Winslow", pii, "person")),
                        "body": (
                            "Please switch alerts to ",
                            Ent("avery.winslow@example.com", pii, "email"),
                            " and call ",
                            Ent("+1 202 555 0143", pii, "phone"),
                            " if delivery fails.",
                        ),
                        "user": {"login": "avery-winslow-sx"},
                        "html_url": "https://github.com/example-org/sample-service/issues/482",
                        "created_at": "2026-06-18T09:14:55Z",
                    },
                    "repository": {"full_name": "example-org/sample-service"},
                    "sender": {"login": "avery-winslow-sx"},
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-github-webhook-issue-002",
        "github_webhook",
        shape_classes,
        obs(
            excerpt="Issue reports a leaked token in reproduction steps.",
            title="Token leak report",
            author=(Ent("Avery Winslow", pii, "person"),),
            source_id="github",
            ref="issues/483",
            url="https://github.com/example-org/sample-service/issues/483",
            kind="issue",
            timestamp="2026-06-18T10:05:00Z",
            provider_event_id="1c9d8e7f-6a5b-4c3d-2e1f-0a9b8c7d6e5f",
            provider_resource_id="I_kwDOExample483",
            evidence_id="ev-gh-issue-483",
            metadata={
                "webhook": {
                    "action": "opened",
                    "issue": {
                        "number": 483,
                        "title": "Token leak report",
                        "body": (
                            "A classic token ",
                            Ent(GITHUB_PAT, "secret", "github-pat", True),
                            " leaked into the reproduction steps.",
                        ),
                        "user": {"login": "avery-winslow-sx"},
                        "html_url": "https://github.com/example-org/sample-service/issues/483",
                        "created_at": "2026-06-18T10:04:52Z",
                    },
                    "repository": {"full_name": "example-org/sample-service"},
                    "sender": {"login": "avery-winslow-sx"},
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-github-webhook-comment-001",
        "github_webhook",
        shape_classes,
        obs(
            excerpt="New comment on the retry queue issue.",
            title="Retry queue drains slowly",
            author="dana-frost-dev",
            source_id="github",
            ref="issues/501",
            url="https://github.com/example-org/sample-service/issues/501",
            kind="issue_comment",
            timestamp="2026-06-19T08:30:00Z",
            provider_event_id="2b3c4d5e-6f70-4a1b-8c9d-0e1f2a3b4c5d",
            provider_resource_id="IC_kwDOExample9001",
            evidence_id="ev-gh-comment-9001",
            metadata={
                "webhook": {
                    "action": "created",
                    "comment": {
                        "id": 9001,
                        "body": (
                            "Loop in ",
                            Ent("Dana Frost", pii, "person"),
                            " via ",
                            Ent("dana.frost@example.org", pii, "email"),
                            ".",
                        ),
                        "user": {"login": "dana-frost-dev"},
                    },
                    "issue": {"number": 501, "title": "Retry queue drains slowly"},
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-github-webhook-comment-002",
        "github_webhook",
        shape_classes,
        obs(
            excerpt="Comment asks for a call before the release cut.",
            title="Release cut checklist",
            author="rowan-ellery-ops",
            source_id="github",
            ref="issues/502",
            url="https://github.com/example-org/sample-service/issues/502",
            kind="issue_comment",
            timestamp="2026-06-19T09:12:00Z",
            provider_event_id="3c4d5e6f-7081-4b2c-9d0e-1f2a3b4c5d6e",
            provider_resource_id="IC_kwDOExample9002",
            evidence_id="ev-gh-comment-9002",
            metadata={
                "webhook": {
                    "action": "created",
                    "comment": {
                        "id": 9002,
                        "body": (
                            "Call me at ",
                            Ent("+1 202 555 0177", pii, "phone"),
                            " before the release cut.",
                        ),
                        "user": {"login": "rowan-ellery-ops"},
                    },
                    "issue": {"number": 502, "title": "Release cut checklist"},
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-github-poll-001",
        "github_poll",
        shape_classes,
        obs(
            excerpt="Polling cycle returned one updated issue.",
            title="Poll batch 510",
            author="poller",
            source_id="github",
            ref="polls/issues",
            url="https://api.github.com/repos/example-org/sample-service/issues",
            kind="poll",
            timestamp="2026-06-20T06:00:00Z",
            provider_event_id="4d5e6f70-8192-4c3d-0e1f-2a3b4c5d6e7f",
            provider_resource_id="poll-batch-510",
            evidence_id="ev-gh-poll-510",
            metadata={
                "poll": {
                    "etag": 'W/"synthetic-etag-1"',
                    "items": [
                        {
                            "number": 510,
                            "title": ("Access request from ", Ent("Rowan Ellery", pii, "person")),
                            "body": (
                                "Grant scoped access and notify ",
                                Ent("rowan.ellery+alerts@example.org", pii, "email"),
                                ".",
                            ),
                        }
                    ],
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-github-poll-002",
        "github_poll",
        shape_classes,
        obs(
            excerpt="Polling cycle surfaced a pasted card number.",
            title="Poll batch 511",
            author="poller",
            source_id="github",
            ref="polls/issues",
            url="https://api.github.com/repos/example-org/sample-service/issues",
            kind="poll",
            timestamp="2026-06-20T06:15:00Z",
            provider_event_id="5e6f7081-92a3-4d4e-1f2a-3b4c5d6e7f80",
            provider_resource_id="poll-batch-511",
            evidence_id="ev-gh-poll-511",
            metadata={
                "poll": {
                    "etag": 'W/"synthetic-etag-2"',
                    "items": [
                        {
                            "number": 511,
                            "title": "Sandbox order confusion",
                            "body": (
                                "The sandbox order pasted ",
                                Ent(PAN_MC, "credential", "pan", True),
                                " into the description.",
                            ),
                        }
                    ],
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-linear-webhook-001",
        "linear_webhook",
        shape_classes,
        obs(
            excerpt="Linear issue created for the on-call rotation.",
            title="Update the on-call contact",
            author="ops-bot",
            source_id="linear",
            ref="ENG-142",
            url="https://linear.app/example/issue/ENG-142",
            kind="issue",
            timestamp="2026-06-19T14:02:00Z",
            provider_event_id="d4e5f6a7-b8c9-4d0e-9f1a-2b3c4d5e6f70",
            provider_resource_id="b1c2d3e4-f5a6-4b7c-8d9e-0f1a2b3c4d5e",
            evidence_id="ev-lin-eng-142",
            metadata={
                "webhook": {
                    "action": "create",
                    "type": "Issue",
                    "organizationId": "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
                    "webhookTimestamp": 1750341720,
                    "data": {
                        "id": "b1c2d3e4-f5a6-4b7c-8d9e-0f1a2b3c4d5e",
                        "identifier": "ENG-142",
                        "title": "Update the on-call contact",
                        "description": (
                            "Rotate on-call to ",
                            Ent("Sable Norwick", pii, "person"),
                            " reachable at ",
                            Ent("sable.norwick@example.com", pii, "email"),
                            ".",
                        ),
                    },
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-linear-webhook-002",
        "linear_webhook",
        shape_classes,
        obs(
            excerpt="Linear issue updated with a callback number.",
            title="Callback request",
            author="ops-bot",
            source_id="linear",
            ref="ENG-143",
            url="https://linear.app/example/issue/ENG-143",
            kind="issue",
            timestamp="2026-06-19T15:40:00Z",
            provider_event_id="e5f6a7b8-c9d0-4e1f-8a2b-3c4d5e6f7081",
            provider_resource_id="c2d3e4f5-a6b7-4c8d-9e0f-1a2b3c4d5e6f",
            evidence_id="ev-lin-eng-143",
            metadata={
                "webhook": {
                    "action": "update",
                    "type": "Issue",
                    "organizationId": "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
                    "webhookTimestamp": 1750347600,
                    "data": {
                        "id": "c2d3e4f5-a6b7-4c8d-9e0f-1a2b3c4d5e6f",
                        "identifier": "ENG-143",
                        "title": ("Callback for ", Ent("Juniper Hale", pii, "person")),
                        "description": (
                            "Vendor asks for a callback at ",
                            Ent("+1 202 555 0198", pii, "phone"),
                            " today.",
                        ),
                    },
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-linear-graphql-001",
        "linear_graphql",
        shape_classes,
        obs(
            excerpt="GraphQL sync pulled one issue for cleanup.",
            title="Export contact cleanup",
            author="sync-bot",
            source_id="linear",
            ref="ENG-207",
            url="https://linear.app/example/issue/ENG-207",
            kind="issue",
            timestamp="2026-06-21T11:00:00Z",
            provider_event_id="f6a7b8c9-d0e1-4f2a-9b3c-4d5e6f708192",
            provider_resource_id="d3e4f5a6-b7c8-4d9e-8f0a-1b2c3d4e5f60",
            evidence_id="ev-lin-eng-207",
            metadata={
                "graphql": {
                    "data": {
                        "issue": {
                            "id": "d3e4f5a6-b7c8-4d9e-8f0a-1b2c3d4e5f60",
                            "identifier": "ENG-207",
                            "title": "Export contact cleanup",
                            "description": (
                                "Remove ",
                                Ent("Marlowe Quist", pii, "person"),
                                " from the CC list and use ",
                                Ent("ops-handoff@example.org", pii, "email"),
                                " instead.",
                            ),
                        }
                    }
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-linear-graphql-002",
        "linear_graphql",
        shape_classes,
        obs(
            excerpt="GraphQL sync surfaced a pasted integration token.",
            title="Integration note cleanup",
            author="sync-bot",
            source_id="linear",
            ref="ENG-208",
            url="https://linear.app/example/issue/ENG-208",
            kind="issue",
            timestamp="2026-06-21T11:20:00Z",
            provider_event_id="a7b8c9d0-e1f2-4a3b-8c4d-5e6f70819203",
            provider_resource_id="e4f5a6b7-c8d9-4e0f-9a1b-2c3d4e5f6071",
            evidence_id="ev-lin-eng-208",
            metadata={
                "graphql": {
                    "data": {
                        "issue": {
                            "id": "e4f5a6b7-c8d9-4e0f-9a1b-2c3d4e5f6071",
                            "identifier": "ENG-208",
                            "title": "Integration note cleanup",
                            "description": (
                                "The integration note pasted ",
                                Ent(SLACK_TOKEN, "secret", "slack-token", True),
                                " in clear text.",
                            ),
                        }
                    }
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-local-directory-001",
        "local_directory",
        shape_classes,
        obs(
            excerpt="Standup notes imported from the shared drive.",
            title="Standup 2026-06-20",
            author="importer",
            source_id="local-directory",
            ref="notes/standup-2026-06-20.md",
            kind="file",
            timestamp="2026-06-20T09:00:00Z",
            provider_resource_id="notes/standup-2026-06-20.md",
            evidence_id="ev-dir-standup-0620",
            metadata={
                "file": {
                    "path": "notes/standup-2026-06-20.md",
                    "content": (
                        "Standup notes: ",
                        Ent("Avery Winslow", pii, "person"),
                        " owns the demo, backup phone ",
                        Ent("+1 202 555 0186", pii, "phone"),
                        ".",
                    ),
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-local-directory-002",
        "local_directory",
        shape_classes,
        obs(
            excerpt="Retro notes imported with reviewer provenance.",
            title="Retro 2026-06-21",
            author="importer",
            source_id="local-directory",
            ref="notes/retro-2026-06-21.md",
            kind="file",
            timestamp="2026-06-21T09:00:00Z",
            provider_resource_id="notes/retro-2026-06-21.md",
            evidence_id="ev-dir-retro-0621",
            evidence_metadata={
                "note": (
                    "Imported from a drive shared by ",
                    Ent("Dana Frost", pii, "person"),
                    ".",
                )
            },
            metadata={
                "file": {
                    "path": "notes/retro-2026-06-21.md",
                    "content": (
                        "Retro action: send the summary to ",
                        Ent("dana.frost@example.org", pii, "email"),
                        " by Thursday.",
                    ),
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-bounded-document-fetch-001",
        "bounded_document_fetch",
        shape_classes,
        obs(
            excerpt="Bounded fetch captured the rollout document.",
            title="Rollout document",
            author="fetcher",
            source_id="document-fetch",
            ref="docs/rollout",
            url="https://example.com/docs/rollout",
            kind="document",
            timestamp="2026-06-22T10:00:00Z",
            provider_event_id="b8c9d0e1-f2a3-4b4c-9d5e-6f7081920a1b",
            provider_resource_id="doc-rollout-v3",
            evidence_id="ev-doc-rollout-v3",
            metadata={
                "fetch": {
                    "url": "https://example.com/docs/rollout",
                    "content_type": "text/markdown",
                    "body": (
                        "The rollout doc lists ",
                        Ent("Rowan Ellery", pii, "person"),
                        " as approver; send questions to ",
                        Ent("rollout-desk@example.com", pii, "email"),
                        ".",
                    ),
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-bounded-document-fetch-002",
        "bounded_document_fetch",
        shape_classes,
        obs(
            excerpt="Bounded fetch captured the logistics appendix.",
            title="Logistics appendix",
            author="fetcher",
            source_id="document-fetch",
            ref="docs/logistics",
            url="https://example.com/docs/logistics",
            kind="document",
            timestamp="2026-06-22T10:30:00Z",
            provider_event_id="c9d0e1f2-a3b4-4c5d-8e6f-70819203a1b2",
            provider_resource_id="doc-logistics-v1",
            evidence_id="ev-doc-logistics-v1",
            metadata={
                "fetch": {
                    "url": "https://example.com/docs/logistics",
                    "content_type": "text/markdown",
                    "body": (
                        "Hardware returns go to ",
                        Ent("14 Larkspur Court, Fable City, OR 97401", pii, "address"),
                        " with a printed label.",
                    ),
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-observation-001",
        "observation",
        obs_shape_classes,
        obs(
            excerpt=(
                "Handoff recorded: ",
                Ent("Sable Norwick", pii, "person"),
                " now triages intake and forwards summaries to ",
                Ent("sable.norwick@example.com", pii, "email"),
                ".",
            ),
            title="Intake triage handoff",
            author="triage-bot",
            source_id="observation-relay",
            ref="relay/obs-3101",
            kind="relay",
            timestamp="2026-06-23T08:00:00Z",
            provider_event_id="d0e1f2a3-b4c5-4d6e-9f70-819203a1b2c3",
            provider_resource_id="obs-3101",
            evidence_id="ev-obs-3101",
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-observation-002",
        "observation",
        obs_shape_classes,
        obs(
            excerpt=(
                "Latency alert raised from ",
                Ent("192.0.2.120", pii, "ip"),
                "; the on-call pager is ",
                Ent("+1 202 555 0171", pii, "phone"),
                ".",
            ),
            title="Latency alert",
            author="alerting",
            source_id="observation-relay",
            ref="relay/obs-3102",
            kind="relay",
            timestamp="2026-06-23T08:30:00Z",
            provider_event_id="e1f2a3b4-c5d6-4e7f-8081-9203a1b2c3d4",
            provider_resource_id="obs-3102",
            evidence_id="ev-obs-3102",
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-observation-003",
        "observation",
        obs_shape_classes,
        obs(
            excerpt=(
                "Billing review paused for account ",
                Ent("77245980", pii, "account_id"),
                " pending confirmation.",
            ),
            title="Billing review pause",
            author=(Ent("Juniper Hale", pii, "person"),),
            source_id="observation-relay",
            ref="relay/obs-3103",
            kind="relay",
            timestamp="2026-06-23T09:00:00Z",
            provider_event_id="f2a3b4c5-d6e7-4f80-8192-03a1b2c3d4e5",
            provider_resource_id="obs-3103",
            evidence_id="ev-obs-3103",
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-adapter-emission-001",
        "adapter_emission",
        shape_classes,
        obs(
            excerpt="Emission drafted for the contact rotation.",
            title="Contact rotation emission",
            author="adapter",
            source_id="adapter",
            ref="emissions/em-7301",
            kind="emission",
            timestamp="2026-06-24T12:00:00Z",
            provider_event_id="a3b4c5d6-e7f8-4a91-8203-a1b2c3d4e5f6",
            provider_resource_id="em-7301",
            evidence_id="ev-em-7301",
            metadata={
                "emission": {
                    "title": ("Contact rotation for ", Ent("Sable Norwick", pii, "person")),
                    "body": (
                        "Route pages to ",
                        Ent("sable.norwick@example.com", pii, "email"),
                        " until Friday.",
                    ),
                    "evidence": [
                        {
                            "excerpt": (
                                "Pager test from ",
                                Ent("+1 202 555 0195", pii, "phone"),
                                " succeeded.",
                            )
                        }
                    ],
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-adapter-emission-002",
        "adapter_emission",
        shape_classes,
        obs(
            excerpt="Emission flagged a storage connection string.",
            title="Storage connection audit",
            author="adapter",
            source_id="adapter",
            ref="emissions/em-7302",
            kind="emission",
            timestamp="2026-06-24T12:30:00Z",
            provider_event_id="b4c5d6e7-f8a9-4ba2-9314-b2c3d4e5f607",
            provider_resource_id="em-7302",
            evidence_id="ev-em-7302",
            metadata={
                "emission": {
                    "title": "Storage connection audit",
                    "body": (
                        "The staging config embedded ",
                        Ent(AZURE_KEY, "secret", "azure-storage-key", True),
                        " verbatim.",
                    ),
                    "evidence": [{"excerpt": "Config diff attached for review."}],
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-external-ingest-envelope-001",
        "external_ingest_envelope",
        shape_classes,
        obs(
            excerpt="Envelope staged for external ingest review.",
            title="External ingest draft",
            author="ingest",
            source_id="external-ingest",
            ref="envelopes/env-8401",
            kind="envelope",
            timestamp="2026-06-25T13:00:00Z",
            provider_event_id="c5d6e7f8-a9b0-4cb3-8425-c3d4e5f60718",
            provider_resource_id="env-8401",
            evidence_id="ev-env-8401",
            metadata={
                "envelope": {
                    "content": (
                        "Envelope drafted by ",
                        Ent("Avery Winslow", pii, "person"),
                        " for review.",
                    ),
                    "candidate_hints": [
                        {
                            "body": (
                                "Hint references ",
                                Ent("dana.frost@example.org", pii, "email"),
                                " for follow-up.",
                            )
                        }
                    ],
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )
    add(
        "shape-external-ingest-envelope-002",
        "external_ingest_envelope",
        shape_classes,
        obs(
            excerpt="Envelope staged with a courier callback hint.",
            title="Courier callback envelope",
            author="ingest",
            source_id="external-ingest",
            ref="envelopes/env-8402",
            kind="envelope",
            timestamp="2026-06-25T13:30:00Z",
            provider_event_id="d6e7f8a9-b0c1-4dc4-9536-d4e5f6071829",
            provider_resource_id="env-8402",
            evidence_id="ev-env-8402",
            metadata={
                "envelope": {
                    "content": (
                        "Courier window confirmed for ",
                        Ent("82 Quill Hollow Road, Ashvale, VT 05901", pii, "address"),
                        " on Tuesday.",
                    ),
                    "candidate_hints": [
                        {
                            "body": (
                                "Callback owner is ",
                                Ent("Marlowe Quist", pii, "person"),
                                ".",
                            )
                        }
                    ],
                }
            },
        ),
        protect=PROTECT_IDENTITY,
    )

    # -- C. decision preservation ---------------------------------------------
    dp = ("decision_preservation", "positive_detection")
    add(
        "decision-person-email-001",
        "observation",
        dp,
        obs(
            excerpt=(
                "Approved: keep the event store local-only for alpha. Contact ",
                Ent("Avery Winslow", pii, "person"),
                " (",
                Ent("avery.winslow@example.com", pii, "email"),
                ") for rollout.",
            )
        ),
        preserve=(("excerpt", "keep the event store local-only for alpha"),),
    )
    add(
        "constraint-phone-001",
        "observation",
        dp,
        obs(
            excerpt=(
                "Constraint: sync intervals stay at 15 minutes or slower. Escalate by phone to ",
                Ent("+1 202 555 0177", pii, "phone"),
                ".",
            )
        ),
        preserve=(("excerpt", "sync intervals stay at 15 minutes or slower"),),
    )
    add(
        "requirement-address-001",
        "observation",
        dp,
        obs(
            excerpt=(
                "Requirement: alpha hardware ships only within the pilot region. Courier drop-off at ",
                Ent("14 Larkspur Court, Fable City, OR 97401", pii, "address"),
                ".",
            )
        ),
        preserve=(("excerpt", "alpha hardware ships only within the pilot region"),),
    )
    add(
        "proposal-pan-001",
        "observation",
        dp,
        obs(
            excerpt=(
                "Proposal: migrate billing exports to the ledger service next sprint. A test capture used card ",
                Ent(PAN_MC, "credential", "pan", True),
                ".",
            )
        ),
        preserve=(("excerpt", "migrate billing exports to the ledger service next sprint"),),
    )
    add(
        "decision-mrn-001",
        "observation",
        dp,
        obs(
            excerpt=(
                "Decision: intake forms are archived after ninety days. A sample chart referenced ",
                Ent(MRN_TEXT, "phi", "mrn", True),
                " during review.",
            )
        ),
        preserve=(("excerpt", "intake forms are archived after ninety days"),),
    )
    add(
        "constraint-secret-001",
        "observation",
        dp,
        obs(
            excerpt=(
                "Constraint: rotate deployment credentials before the freeze. A leaked test key ",
                Ent(AWS_KEY, "secret", "aws-access-key", True),
                " was revoked.",
            )
        ),
        preserve=(("excerpt", "rotate deployment credentials before the freeze"),),
    )
    add(
        "requirement-email-person-001",
        "observation",
        dp,
        obs(
            excerpt=(
                "Requirement: every incident gets a named scribe. ",
                Ent("Rowan Ellery", pii, "person"),
                " volunteers and reads ",
                Ent("rowan.ellery+alerts@example.org", pii, "email"),
                " during drills.",
            )
        ),
        preserve=(("excerpt", "every incident gets a named scribe"),),
    )
    add(
        "proposal-ip-001",
        "observation",
        dp,
        obs(
            excerpt=(
                "Proposal: pin the collector to a static address next quarter. The current probe runs from ",
                Ent("192.0.2.61", pii, "ip"),
                ".",
            )
        ),
        preserve=(("excerpt", "pin the collector to a static address next quarter"),),
    )

    # -- D. negative controls -------------------------------------------------
    neg = ("negative_control",)

    def add_neg(record_id: str, excerpt: Any) -> None:
        add(record_id, "plain_text", neg, obs(excerpt=excerpt), outcome="unchanged")

    add_neg(
        "neg-git-sha-001",
        "Deployed commit 3f9c2b7e1a4d5c6f8091a2b3c4d5e6f708192a3b to staging.",
    )
    add_neg(
        "neg-uuid-002",
        "Correlation id 0f7c4d2a-9b1e-4c3d-8a5f-6e7d8c9b0a1f covers the retry.",
    )
    add_neg(
        "neg-timestamp-003",
        "The window opens 2026-07-01T12:00:00Z and closes 2026-07-02T12:00:00Z.",
    )
    add_neg(
        "neg-fingerprint-004",
        "Semantic fingerprint fp:sha256:9c1e2d3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8091a2b3 matched.",
    )
    add_neg("neg-contract-id-005", "Change tracked under CT-2026-0041 pending sign-off.")
    add_neg("neg-receipt-id-006", "Receipt rcpt-2026-06-30-0007 archived with the bundle.")
    add_neg("neg-issue-refs-007", "Fixes #269 and follows up on PR #281.")
    add_neg(
        "neg-file-path-008",
        "See adapter/core/redaction_receipt.py and tests/redaction_evaluation/README.md.",
    )
    add_neg(
        "neg-repo-name-009",
        "Mirrored from BicameralAI/bicameral-integrations at the last release.",
    )
    add_neg(
        "neg-url-010",
        "Documentation moved to https://example.com/docs/adapter-boundary today.",
    )
    add_neg("neg-version-011", "Pinned versions v2.25.0 and 3.13.7 for the pilot.")
    add_neg(
        "neg-code-snippet-012",
        "def total(items):\n    return sum(item.count for item in items)\n",
    )
    add_neg(
        "neg-numeric-labeled-013",
        "order_id: 4111111111111112 recorded; run 12345678901234 finished; "
        "batch 9999999999999999999999 exceeds the PAN length window.",
    )
    add_neg(
        "neg-provider-resource-014",
        "Provider resource I_kwDOExample501 tracked; node MDU6TGFiZWwxMjM0 unchanged.",
    )

    # -- E. failure and resilience --------------------------------------------
    add(
        "malformed-unicode-lone-surrogate",
        "failure_fixture",
        ("malformed_input",),
        obs(excerpt="Payload fragment \ud800 arrived truncated mid-stream."),
        outcome="failed_closed",
        failure_reason="unsupported_payload",
    )

    deep_leaf: Any = (
        "Escalation contact ",
        Ent("dana.frost@example.org", pii, "email"),
        " for the pilot.",
    )
    deep_node: Any = deep_leaf
    for _ in range(64):
        deep_node = {"a": deep_node}
    add(
        "deeply-nested-metadata-64",
        "failure_fixture",
        ("nested_metadata", "positive_detection"),
        obs(excerpt="Deep metadata resilience probe.", metadata=deep_node),
    )

    add(
        "unsupported-binary-value",
        "failure_fixture",
        ("unsupported_binary",),
        obs(
            excerpt="Attachment ingest carried an undecodable payload.",
            metadata={"blob": "AAECAwQFBgc="},
        ),
        outcome="failed_closed",
        failure_reason="unsupported_binary",
        directives={"binary_field": {"path": "metadata.blob", "base64": "AAECAwQFBgc="}},
    )

    oversized_sentence = "Synthetic rollout telemetry line for the oversized payload probe. "
    add(
        "oversized-payload",
        "failure_fixture",
        ("oversized_payload",),
        obs(excerpt=oversized_sentence * 17000),
        outcome="failed_closed",
        failure_reason="oversized_payload",
    )

    add(
        "sensitive-metadata-key-token",
        "failure_fixture",
        ("sensitive_metadata_key",),
        obs(excerpt="Metadata carried an unsafe key name.", metadata={}),
        outcome="failed_closed",
        failure_reason="sensitive_metadata_key",
        directives=_obfuscated_object_directive(
            "metadata",
            {AWS_KEY: "flagged during the scan", "note": "rotate immediately"},
        ),
    )
    add(
        "sensitive-metadata-key-phi",
        "failure_fixture",
        ("sensitive_metadata_key",),
        obs(excerpt="Metadata carried a labeled clinical key.", metadata={}),
        outcome="failed_closed",
        failure_reason="sensitive_metadata_key",
        directives=_obfuscated_object_directive(
            "metadata",
            {PHI_KEY_TEXT: "row exported in error", "note": "clinical label appeared in a key"},
        ),
    )

    backend_faults: tuple[tuple[str, str, str, str], ...] = (
        (
            "backend-invalid-configuration",
            "invalid_configuration",
            "backend_invalid_configuration",
            "backend_invalid_configuration",
        ),
        ("backend-missing-model", "missing_model", "backend_unavailable", "backend_unavailable"),
        (
            "backend-initialization-failure",
            "init_failure",
            "backend_unavailable",
            "backend_unavailable",
        ),
        ("backend-exception", "exception", "backend_crash", "backend_crash"),
        ("backend-timeout", "hang", "backend_timeout", "backend_timeout"),
        ("worker-crash", "worker_crash", "backend_crash", "backend_crash"),
        (
            "concurrent-timeout-storm",
            "timeout_storm",
            "backend_timeout",
            "concurrency_timeout_storm",
        ),
        (
            "malformed-spans-out-of-range",
            "malformed_spans_out_of_range",
            "malformed_backend_findings",
            "malformed_backend_findings",
        ),
        (
            "malformed-spans-overlapping",
            "malformed_spans_overlapping",
            "malformed_backend_findings",
            "malformed_backend_findings",
        ),
        (
            "nondeterministic-output-probe",
            "nondeterministic",
            "nondeterministic_backend_output",
            "nondeterminism_probe",
        ),
    )
    for record_id, fault, reason, cls in backend_faults:
        add(
            record_id,
            "failure_fixture",
            (cls,),
            obs(excerpt="A clean fixture sentence for backend fault injection."),
            outcome="failed_closed",
            failure_reason=reason,
            directives={"fault": fault},
        )

    return records


# --- serialization and validation ---------------------------------------------


def _dump_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode(
        "ascii"
    )


def _sha256_label(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _resolve(observation: dict[str, Any], path: str) -> Any:
    return _LOADER.resolve_field_path(observation, path)


def _iter_strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        found: list[str] = []
        for key, value in node.items():
            found.append(str(key))
            found.extend(_iter_strings(value))
        return found
    if isinstance(node, list):
        found = []
        for item in node:
            found.extend(_iter_strings(item))
        return found
    return []


def _build_expected(
    spec: RecordSpec,
    plain_observation: dict[str, Any],
    entities: list[tuple[str, int, int, Ent]],
) -> dict[str, Any]:
    expected_entities = [
        {
            "entity_id": f"e{index:03d}",
            "category": ent.category,
            "subtype": ent.subtype,
            "field_path": path,
            "start": start,
            "end": end,
            "replacement": f"[redacted:{ent.subtype}]",
            "mandatory": ent.mandatory,
        }
        for index, (path, start, end, ent) in enumerate(entities, start=1)
    ]
    protected = []
    for path in spec.protect:
        value = _resolve(plain_observation, path)
        if not isinstance(value, str):
            raise AssertionError(f"{spec.record_id}: protected field {path} is not a string")
        if value == "":
            continue
        protected.append(
            {
                "field_path": path,
                "expected_value_sha256": _sha256_label(
                    json.dumps(
                        value,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode("utf-8")
                ),
            }
        )
    preservation = [
        {
            "assertion_id": f"preserve-{index:03d}",
            "field_path": path,
            "required_substring": substring,
        }
        for index, (path, substring) in enumerate(spec.preserve, start=1)
    ]
    return {
        "schema_version": 1,
        "record_id": spec.record_id,
        "expected_entities": expected_entities,
        "protected_fields": protected,
        "preservation_assertions": preservation,
        "expected_outcome": spec.outcome,
        "expected_failure_reason": spec.failure_reason,
    }


def _validate_spec(
    spec: RecordSpec,
    plain_observation: dict[str, Any],
    entities: list[tuple[str, int, int, Ent]],
    expected: dict[str, Any],
) -> None:
    rid = spec.record_id
    if (spec.outcome == "failed_closed") != (spec.failure_reason is not None):
        raise AssertionError(f"{rid}: outcome/failure_reason mismatch")
    for path, start, end, ent in entities:
        if len(path) > FIELD_PATH_MAX:
            raise AssertionError(f"{rid}: field path too long: {path}")
        text = _resolve(plain_observation, path)
        if not isinstance(text, str):
            raise AssertionError(f"{rid}: entity field {path} is not a string")
        if not (0 <= start < end <= len(text)):
            raise AssertionError(f"{rid}: bad span {start}:{end} at {path}")
        if text[start:end] != ent.text:
            raise AssertionError(f"{rid}: span text mismatch at {path}")
        if ent.mandatory and not detect_sensitive(text):
            raise AssertionError(
                f"{rid}: mandatory {ent.subtype} does not trip the catalog at {path}"
            )
    for path, substring in spec.preserve:
        text = _resolve(plain_observation, path)
        if not isinstance(text, str):
            raise AssertionError(f"{rid}: preservation field {path} is not a string")
        spans = [
            (start, end) for epath, start, end, _ in entities if epath == path
        ]
        clear = False
        offset = text.find(substring)
        while offset != -1:
            candidate = (offset, offset + len(substring))
            if all(
                not (candidate[0] < end and start < candidate[1]) for start, end in spans
            ):
                clear = True
                break
            offset = text.find(substring, offset + 1)
        if not clear:
            raise AssertionError(
                f"{rid}: preservation substring missing or overlapping at {path}"
            )
    if "negative_control" in spec.classes:
        if entities:
            raise AssertionError(f"{rid}: negative control must not carry entities")
        for text in _iter_strings(plain_observation):
            if detect_sensitive(text):
                raise AssertionError(f"{rid}: negative control trips the catalog")
    if spec.outcome != "sanitized" and entities and rid != "deeply-nested-metadata-64":
        raise AssertionError(f"{rid}: non-sanitized record carries entities")
    if expected["record_id"] != rid:
        raise AssertionError(f"{rid}: expected record id mismatch")


def _scan_committed_tree() -> None:
    """Every committed byte in this package must pass the sensitive catalog."""
    for path in sorted(BASE.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts:
            continue
        if path.suffix not in {".py", ".json", ".md"}:
            continue
        text = path.read_bytes().decode("utf-8")
        hits = detect_sensitive(text)
        if hits:
            raise AssertionError(
                f"committed file trips the sensitive catalog: {path.name}: "
                f"{[(hit.cls, hit.pattern_id) for hit in hits]}"
            )


def _optional_jsonschema_validation(
    manifest: dict[str, Any], expected_records: list[dict[str, Any]]
) -> None:
    try:
        import jsonschema
    except ImportError:
        return
    manifest_schema = json.loads(
        (BASE / "schema" / "corpus-manifest.schema.json").read_text(encoding="utf-8")
    )
    expected_schema = json.loads(
        (BASE / "schema" / "expected-record.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(manifest, manifest_schema)
    for record in expected_records:
        jsonschema.validate(record, expected_schema)


def main() -> None:
    specs = build_records()
    record_ids = [spec.record_id for spec in specs]
    if len(set(record_ids)) != len(record_ids):
        raise AssertionError("duplicate record ids")

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    manifest_records: list[dict[str, Any]] = []
    expected_records: list[dict[str, Any]] = []
    total_bytes = 0

    for spec in sorted(specs, key=lambda item: item.record_id):
        flat = FlattenResult()
        plain_observation = _flatten(spec.observation, "", flat)
        expected = _build_expected(spec, plain_observation, flat.entities)
        _validate_spec(spec, plain_observation, flat.entities, expected)

        input_record: dict[str, Any] = {
            "record_id": spec.record_id,
            "source_shape": spec.source_shape,
            "observation": _obfuscate_committed(plain_observation),
        }
        if spec.directives is not None:
            input_record["eval_directives"] = spec.directives

        input_bytes = _dump_bytes(input_record)
        expected_bytes = _dump_bytes(expected)
        input_path = CORPUS_DIR / f"{spec.record_id}.json"
        expected_path = EXPECTED_DIR / f"{spec.record_id}.json"
        input_path.write_bytes(input_bytes)
        expected_path.write_bytes(expected_bytes)
        total_bytes += len(input_bytes) + len(expected_bytes)

        manifest_records.append(
            {
                "record_id": spec.record_id,
                "source_shape": spec.source_shape,
                "input_path": f"{REL_CORPUS}/{spec.record_id}.json",
                "expected_path": f"{REL_EXPECTED}/{spec.record_id}.json",
                "classes": list(spec.classes),
                "input_sha256": _sha256_label(input_bytes),
                "expected_sha256": _sha256_label(expected_bytes),
            }
        )
        expected_records.append(expected)

    manifest = {
        "schema_version": 1,
        "corpus_id": CORPUS_ID,
        "description": CORPUS_DESCRIPTION,
        "records": manifest_records,
    }
    manifest_bytes = _dump_bytes(manifest)
    MANIFEST_PATH.write_bytes(manifest_bytes)
    total_bytes += len(manifest_bytes)

    # Remove stale record files so the tree exactly mirrors the manifest.
    keep = {f"{record_id}.json" for record_id in record_ids}
    for directory in (CORPUS_DIR, EXPECTED_DIR):
        for path in sorted(directory.glob("*.json")):
            if path.name not in keep:
                path.unlink()

    # Post-write verification: digests, loader round-trip, committed-byte scan.
    for entry in manifest_records:
        input_disk = (REPO_ROOT / entry["input_path"]).read_bytes()
        expected_disk = (REPO_ROOT / entry["expected_path"]).read_bytes()
        if _sha256_label(input_disk) != entry["input_sha256"]:
            raise AssertionError(f"{entry['record_id']}: input digest drift")
        if _sha256_label(expected_disk) != entry["expected_sha256"]:
            raise AssertionError(f"{entry['record_id']}: expected digest drift")
        loaded = _LOADER.load_input_record(REPO_ROOT / entry["input_path"])
        if loaded["record_id"] != entry["record_id"]:
            raise AssertionError(f"{entry['record_id']}: loader round-trip mismatch")

    _optional_jsonschema_validation(manifest, expected_records)
    _scan_committed_tree()

    corpus_digest = hashlib.sha256(
        "".join(
            entry["input_sha256"] + entry["expected_sha256"] for entry in manifest_records
        ).encode("ascii")
    ).hexdigest()
    print(
        f"records={len(manifest_records)} total_bytes={total_bytes} "
        f"corpus_digest=sha256:{corpus_digest}"
    )


if __name__ == "__main__":
    main()
    sys.exit(0)
