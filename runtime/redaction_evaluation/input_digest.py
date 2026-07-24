# SPDX-License-Identifier: MIT
"""Deterministic evaluation-input digest for the ADR-0020 redaction evaluation.

``compute_evaluation_input_digest`` binds every input that determines the
evaluation outcome into one canonical ``sha256`` value:

- the corpus manifest bytes, every corpus input file, and every expected
  annotation file the manifest declares;
- every evaluation schema under ``tests/redaction_evaluation/schema/``;
- each candidate's declared configuration digest (computed from the statically
  pinned identity a backend builds in ``__init__``; no model is loaded and no
  heavy dependency is imported);
- the candidate-neutral policy manifest;
- the evaluator code itself (every ``.py`` under
  ``runtime/redaction_evaluation/`` plus the orchestrator, the memory
  measurement script, and the corpus loader/generator);
- the statically pinned package and model identities per candidate.

The digest is a pure function of the bound bytes and pinned identities: no
timestamps, no environment probes. Any byte change in any bound input changes
``evaluation_input_sha256``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .backends import CANDIDATE_IDS, create_backend
from .policy import LabelMap, RedactionPolicy, configuration_digest

SCHEMA_VERSION = 1

_MANIFEST_REL = Path("tests") / "redaction_evaluation" / "corpus-manifest.json"
_SCHEMA_DIR_REL = Path("tests") / "redaction_evaluation" / "schema"
_EVALUATOR_CODE_DIR_REL = Path("runtime") / "redaction_evaluation"
_EVALUATOR_EXTRA_FILES = (
    "scripts/evaluate_redaction_backends.py",
    "scripts/measure_redaction_memory.py",
    "tests/redaction_evaluation/corpus_loader.py",
    "tests/redaction_evaluation/generate_corpus.py",
)


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _corpus_file_digests(
    repo_root: Path, manifest: dict[str, Any]
) -> dict[str, str]:
    """Digest every manifest-declared input and expected annotation file."""

    digests: dict[str, str] = {}
    for record in manifest.get("records", []):
        for key in ("input_path", "expected_path"):
            relative = str(record[key])
            file_path = repo_root / relative
            if not file_path.is_file():
                raise FileNotFoundError(
                    f"corpus manifest references a missing file: {relative}"
                )
            digests[Path(relative).as_posix()] = _sha256_path(file_path)
    return digests


def _schema_file_digests(repo_root: Path) -> dict[str, str]:
    schema_dir = repo_root / _SCHEMA_DIR_REL
    digests: dict[str, str] = {}
    for path in sorted(schema_dir.glob("*.json")):
        digests[path.relative_to(repo_root).as_posix()] = _sha256_path(path)
    return digests


def _evaluator_code_digests(repo_root: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    code_dir = repo_root / _EVALUATOR_CODE_DIR_REL
    if code_dir.is_dir():
        for path in sorted(code_dir.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            digests[path.relative_to(repo_root).as_posix()] = _sha256_path(path)
    for relative in _EVALUATOR_EXTRA_FILES:
        path = repo_root / relative
        if path.is_file():
            digests[Path(relative).as_posix()] = _sha256_path(path)
    return digests


def _candidate_identity_blocks(
    policy: RedactionPolicy,
) -> tuple[dict[str, str], dict[str, dict[str, dict[str, str]]]]:
    """Per-candidate configuration digests plus static package/model pins.

    Backends construct their pinned identity in ``__init__`` without importing
    heavy dependencies and without ``initialize()``; this binds the *declared*
    configuration (for the datafog lane the runtime-measured
    ``patterns_digest`` is deliberately empty at this stage, so the bound
    value is the static declaration, not a model-load product).
    """

    config_digests: dict[str, str] = {}
    identities: dict[str, dict[str, dict[str, str]]] = {}
    for candidate_id in CANDIDATE_IDS:
        backend = create_backend(candidate_id)
        identity = backend.identity
        label_map = getattr(backend, "label_map", None)
        if not isinstance(label_map, LabelMap):
            label_map = LabelMap(map_id=f"{candidate_id}-labels-unversioned")
        config_digests[candidate_id] = configuration_digest(
            dict(identity.configuration), label_map, policy
        )
        identities[candidate_id] = {
            "packages": dict(identity.packages),
            "models": dict(identity.models),
        }
    return config_digests, identities


def compute_evaluation_input_digest(
    repo_root: Path, *, policy: RedactionPolicy | None = None
) -> dict[str, Any]:
    """Bind every evaluation input into one canonical digest document.

    Returns ``{"schema_version": 1, "evaluation_input_sha256": "sha256:...",
    "bound": {...}}`` where ``bound`` is the canonical (path -> sha256 of
    bytes) map plus the identity blocks described in the module docstring.
    The digest is ``sha256`` over the canonical sorted JSON serialization of
    ``bound``.
    """

    repo_root = Path(repo_root)
    active_policy = policy if policy is not None else RedactionPolicy()

    manifest_path = repo_root / _MANIFEST_REL
    if not manifest_path.is_file():
        raise FileNotFoundError(f"corpus manifest missing: {manifest_path}")
    manifest_digest = _sha256_path(manifest_path)
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))

    config_digests, identities = _candidate_identity_blocks(active_policy)

    bound: dict[str, Any] = {
        "corpus_manifest_sha256": manifest_digest,
        "corpus_files": _corpus_file_digests(repo_root, manifest),
        "schema_files": _schema_file_digests(repo_root),
        "candidate_configurations": config_digests,
        "pinned_identities": identities,
        "policy_manifest": active_policy.manifest(),
        "evaluator_code": _evaluator_code_digests(repo_root),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluation_input_sha256": _sha256_bytes(_canonical(bound).encode("utf-8")),
        "bound": bound,
    }
