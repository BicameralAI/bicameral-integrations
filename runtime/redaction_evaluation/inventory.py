# SPDX-License-Identifier: MIT
"""Dependency, license, and vulnerability inventory for candidate backends.

Runs inside the evaluation venv and produces three JSON-serializable
documents: a dependency report (every installed distribution classified
direct/transitive per candidate, plus model artifacts), a license report
(pip-licenses merged with importlib.metadata, judged against a pinned
distribution-compatibility policy), and a vulnerability report (pip-audit
plus a static known-advisories section grounded in installed versions).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

CANDIDATE_TOP_LEVEL_PACKAGES: dict[str, tuple[str, ...]] = {
    "bicameral-stdlib-v1": (),
    "presidio-spacy-lg-v1": (
        "presidio-analyzer",
        "presidio-anonymizer",
        "spacy",
        "en-core-web-lg",
        "en-core-web-sm",
    ),
    "presidio-gliner-pii-v1": (
        "presidio-analyzer",
        "gliner",
        "torch",
        "transformers",
        "onnxruntime",
        "en-core-web-sm",
    ),
    "datafog-regex-v1": ("datafog",),
}

_COMPATIBLE_LICENSE_MARKERS = (
    "mit",
    "bsd",
    "apache",
    "isc",
    "psf",
    "python software foundation",
)
_INCOMPATIBLE_LICENSE_MARKERS = ("agpl", "sspl", "cc-by-nc", "gpl")
_HASH_LIMIT_BYTES = 2 * 1024**3
_SPACY_MODEL_PREFIX = "en-core-web"

_UPDATE_PROCEDURE = (
    "Update: change the pin in the evaluation venv with "
    "'pip install --force-reinstall <package>==<new-version>', re-provision "
    "any model artifacts offline, then re-run the full hard-gate evaluation "
    "(determinism, offline proof, benchmarks) before adopting the new pin."
)
_ROLLBACK_PROCEDURE = (
    "Rollback: reinstall the previous pin with "
    "'pip install --force-reinstall <package>==<previous-version>' and "
    "restore the previously cached model artifacts; the recorded "
    "configuration digest must return to its prior value before the "
    "rollback is considered complete."
)


def _normalize(name: str) -> str:
    """PEP 503 project-name normalization."""

    return re.sub(r"[-_.]+", "-", name).lower()


_REQUIREMENT_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _requirement_name(requirement: str) -> str | None:
    match = _REQUIREMENT_NAME_RE.match(requirement)
    return _normalize(match.group(1)) if match else None


def resolve_distribution(name: str) -> Any | None:
    """Best-effort lookup of an installed distribution by (any-case) name."""

    import importlib.metadata as importlib_metadata

    try:
        return importlib_metadata.distribution(name)
    except importlib_metadata.PackageNotFoundError:
        return None


def distribution_files_bytes(dist: Any) -> int | None:
    """Sum of on-disk sizes of a distribution's recorded files."""

    files = dist.files
    if not files:
        return None
    total = 0
    for entry in files:
        try:
            located = Path(str(entry.locate()))
            if located.is_file():
                total += located.stat().st_size
        except OSError:
            continue
    return total


def directory_size_bytes(path: Path) -> int:
    """Recursive on-disk size of a directory, skipping unreadable entries."""

    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def hf_cache_dir() -> Path | None:
    """Locate the Hugging Face hub cache directory, best-effort."""

    override = os.environ.get("HF_HUB_CACHE")
    if override:
        return Path(override)
    try:
        from huggingface_hub.constants import (  # type: ignore[import-not-found]
            HF_HUB_CACHE,
        )

        return Path(HF_HUB_CACHE)
    except Exception:
        fallback = Path.home() / ".cache" / "huggingface" / "hub"
        return fallback if fallback.exists() else None


def _sha256_file(path: Path) -> str | None:
    """sha256 of one file; ``None`` when the file is 2 GiB or larger."""

    if path.stat().st_size >= _HASH_LIMIT_BYTES:
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _installed_distributions() -> dict[str, Any]:
    import importlib.metadata as importlib_metadata

    dists: dict[str, Any] = {}
    for dist in importlib_metadata.distributions():
        name = dist.metadata["Name"]
        if not name:
            continue
        dists.setdefault(_normalize(str(name)), dist)
    return dists


def _dependency_closure(
    top_level: tuple[str, ...], dists: dict[str, Any]
) -> set[str]:
    """Transitive closure over Requires-Dist, skipping extra-only requirements."""

    stack = [name for name in (_normalize(t) for t in top_level) if name in dists]
    closure: set[str] = set()
    while stack:
        name = stack.pop()
        if name in closure:
            continue
        closure.add(name)
        for requirement in dists[name].requires or []:
            if "extra ==" in requirement:
                continue
            required = _requirement_name(requirement)
            if required and required in dists and required not in closure:
                stack.append(required)
    return closure


def _classify_license(license_text: str) -> str:
    """Classify one license string: compatible | incompatible | unknown."""

    lowered = license_text.lower().strip()
    if not lowered or lowered in ("unknown", "undefined"):
        return "unknown"
    if "lgpl" in lowered:
        # LGPL is on neither pinned list; route to human review, never guess.
        return "unknown"
    if any(marker in lowered for marker in _INCOMPATIBLE_LICENSE_MARKERS):
        return "incompatible"
    if any(marker in lowered for marker in _COMPATIBLE_LICENSE_MARKERS):
        return "compatible"
    return "unknown"


def _effective_license(
    classifiers: list[str],
    pip_license: str | None,
    metadata_license: str | None,
) -> str:
    if classifiers:
        return "; ".join(c.split("::")[-1].strip() for c in classifiers)
    if pip_license and pip_license.strip().upper() != "UNKNOWN":
        return pip_license.strip()
    if metadata_license:
        text = metadata_license.strip()
        # Long values are usually full license text pasted into metadata;
        # those need eyes, not substring matching.
        if text and len(text) <= 200:
            return text
    return "unknown"


def _spacy_model_artifact(name: str) -> dict[str, Any]:
    dist = resolve_distribution(name)
    if dist is None:
        return {
            "name": name,
            "kind": "spacy-pipeline-package",
            "status": "not-installed",
        }
    files = sorted(str(entry) for entry in (dist.files or []))
    digest = hashlib.sha256()
    for relative in files:
        try:
            located = Path(str(dist.locate_file(relative)))
            if not located.is_file():
                continue
            file_digest = _sha256_file(located)
        except OSError:
            continue
        if file_digest is None:
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\n")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\n")
    return {
        "name": name,
        "kind": "spacy-pipeline-package",
        "status": "installed",
        "version": dist.version,
        "path_basis": "importlib.metadata distribution files",
        "bytes": distribution_files_bytes(dist),
        "sha256": digest.hexdigest(),
        "sha256_basis": (
            "sha256 over sorted (relative path, file sha256) pairs for the "
            "distribution's files under 2 GiB"
        ),
    }


def _gliner_model_artifacts() -> list[dict[str, Any]]:
    cache = hf_cache_dir()
    if cache is None or not cache.exists():
        return [
            {
                "name": "gliner-model",
                "kind": "hf-cached-model",
                "status": "hf-cache-not-found",
            }
        ]
    artifacts: list[dict[str, Any]] = []
    for child in sorted(cache.iterdir(), key=lambda p: p.name):
        if not child.is_dir() or "gliner" not in child.name.lower():
            continue
        entry: dict[str, Any] = {
            "name": child.name,
            "kind": "hf-cached-model",
            "status": "cached",
            "path_basis": str(child),
            "bytes": directory_size_bytes(child),
            "bytes_basis": "entire HF cache model directory (blobs + snapshots)",
        }
        weights = sorted(child.rglob("pytorch_model.bin")) or sorted(
            child.rglob("model.safetensors")
        )
        if weights:
            weight = weights[0]
            entry["weights_file"] = weight.name
            entry["weights_bytes"] = weight.stat().st_size
            entry["weights_sha256"] = _sha256_file(weight)
        artifacts.append(entry)
    if not artifacts:
        artifacts.append(
            {
                "name": "gliner-model",
                "kind": "hf-cached-model",
                "status": "not-cached",
            }
        )
    return artifacts


def _build_model_artifacts(candidate_ids: list[str]) -> list[dict[str, Any]]:
    spacy_models: set[str] = set()
    wants_gliner = False
    for candidate_id in candidate_ids:
        for top in CANDIDATE_TOP_LEVEL_PACKAGES[candidate_id]:
            normalized = _normalize(top)
            if normalized.startswith(_SPACY_MODEL_PREFIX):
                spacy_models.add(normalized)
            if normalized == "gliner":
                wants_gliner = True
    artifacts = [_spacy_model_artifact(name) for name in sorted(spacy_models)]
    if wants_gliner:
        artifacts.extend(_gliner_model_artifacts())
    return artifacts


def _build_dependency_report(
    candidate_ids: list[str],
    dists: dict[str, Any],
    closures: dict[str, set[str]],
) -> dict[str, Any]:
    packages: list[dict[str, Any]] = []
    for norm_name in sorted(dists):
        dist = dists[norm_name]
        meta = dist.metadata
        candidate_roles: dict[str, str] = {}
        for candidate_id in candidate_ids:
            tops = {
                _normalize(t)
                for t in CANDIDATE_TOP_LEVEL_PACKAGES[candidate_id]
            }
            if norm_name in closures[candidate_id]:
                candidate_roles[candidate_id] = (
                    "direct" if norm_name in tops else "transitive"
                )
        classifiers = meta.get_all("Classifier") or []
        packages.append(
            {
                "name": str(meta["Name"]),
                "normalized_name": norm_name,
                "version": dist.version,
                "requires": sorted(dist.requires or []),
                "installed_bytes": distribution_files_bytes(dist),
                "requires_python": meta["Requires-Python"],
                "os_classifiers": [
                    c for c in classifiers if c.startswith("Operating System ::")
                ],
                "candidates": candidate_roles,
            }
        )
    return {
        "schema_version": 1,
        "generated_by": "runtime/redaction_evaluation/inventory.py",
        "environment": {"python": sys.version, "platform": platform.platform()},
        "candidate_ids": list(candidate_ids),
        "candidate_top_level_packages": {
            candidate_id: list(CANDIDATE_TOP_LEVEL_PACKAGES[candidate_id])
            for candidate_id in candidate_ids
        },
        "packages": packages,
        "model_artifacts": _build_model_artifacts(candidate_ids),
        "update_procedure": _UPDATE_PROCEDURE,
        "rollback_procedure": _ROLLBACK_PROCEDURE,
    }


def _run_pip_licenses() -> tuple[list[dict[str, Any]] | None, str | None]:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "piplicenses", "--format=json", "--with-urls"],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        detail = completed.stderr.strip()[-500:]
        return None, detail or f"exit_{completed.returncode}"
    try:
        rows = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return None, f"unparseable_output: {exc}"
    if not isinstance(rows, list):
        return None, "unexpected_output_shape"
    return rows, None


def _build_license_report(
    candidate_ids: list[str],
    dists: dict[str, Any],
    closures: dict[str, set[str]],
) -> dict[str, Any]:
    rows, tool_error = _run_pip_licenses()
    rows_by_name: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        rows_by_name[_normalize(str(row.get("Name", "")))] = row

    packages: list[dict[str, Any]] = []
    effective: dict[str, str] = {}
    for norm_name in sorted(dists):
        dist = dists[norm_name]
        meta = dist.metadata
        classifiers = [
            c
            for c in (meta.get_all("Classifier") or [])
            if c.startswith("License ::")
        ]
        metadata_license = meta["License-Expression"] or meta["License"]
        pip_row = rows_by_name.get(norm_name)
        pip_license = str(pip_row["License"]) if pip_row else None
        license_text = _effective_license(classifiers, pip_license, metadata_license)
        effective[norm_name] = license_text
        packages.append(
            {
                "name": str(meta["Name"]),
                "normalized_name": norm_name,
                "version": dist.version,
                "license_pip_licenses": pip_license,
                "license_metadata": (
                    str(metadata_license)[:200] if metadata_license else None
                ),
                "license_classifiers": classifiers,
                "effective_license": license_text,
                "classification": _classify_license(license_text),
                "url": (pip_row or {}).get("URL"),
            }
        )

    candidates: dict[str, Any] = {}
    for candidate_id in candidate_ids:
        closure = sorted(closures[candidate_id])
        incompatible = sorted(
            n for n in closure if _classify_license(effective[n]) == "incompatible"
        )
        unknown = sorted(
            n for n in closure if _classify_license(effective[n]) == "unknown"
        )
        compatible: bool | str
        if incompatible:
            compatible = False
        elif unknown:
            compatible = "review_required"
        else:
            compatible = True
        candidates[candidate_id] = {
            "closure_packages": closure,
            "licenses": sorted({effective[n] for n in closure}),
            "incompatible_packages": incompatible,
            "unknown_license_packages": unknown,
            "compatible_with_distribution": compatible,
        }

    return {
        "schema_version": 1,
        "generated_by": "runtime/redaction_evaluation/inventory.py",
        "tool": {
            "name": "pip-licenses",
            "status": "ok" if rows is not None else "unavailable",
            "error": tool_error,
        },
        "policy": {
            "compatible_markers": list(_COMPATIBLE_LICENSE_MARKERS),
            "incompatible_markers": list(_INCOMPATIBLE_LICENSE_MARKERS),
            "unknown": "review_required",
        },
        "packages": packages,
        "candidates": candidates,
    }


def _run_pip_audit() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip_audit",
                "--format",
                "json",
                "--skip-editable",
                "--progress-spinner",
                "off",
            ],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "reason": f"{type(exc).__name__}: {exc}"}
    stdout = completed.stdout.strip()
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            dependencies = parsed.get("dependencies")
            if isinstance(dependencies, list):
                parsed["dependencies"] = sorted(
                    dependencies, key=lambda d: str(d.get("name", ""))
                )
            return {
                "status": "ok",
                "exit_code": completed.returncode,
                "result": parsed,
            }
    reason = completed.stderr.strip()[-1000:] or f"exit_{completed.returncode}"
    return {"status": "unavailable", "reason": reason}


def _installed_version(name: str) -> str | None:
    dist = resolve_distribution(name)
    return str(dist.version) if dist is not None else None


def _version_tuple(version: str) -> tuple[int, ...] | None:
    parts: list[int] = []
    for piece in version.split(".")[:3]:
        match = re.match(r"\d+", piece)
        if not match:
            break
        parts.append(int(match.group(0)))
    return tuple(parts) if parts else None


def _mitigation_status(
    installed: str | None, fixed_floor: tuple[int, ...]
) -> str:
    if installed is None:
        return "not-installed"
    parsed = _version_tuple(installed)
    if parsed is None:
        return "review_required"
    return "mitigated" if parsed >= fixed_floor else "affected"


def _known_advisories() -> list[dict[str, Any]]:
    torch_version = _installed_version("torch")
    transformers_version = _installed_version("transformers")
    spacy_llm_version = _installed_version("spacy-llm")
    return [
        {
            "id": "CVE-2025-32434",
            "component": "torch",
            "affected": "<2.6",
            "summary": (
                "torch.load could execute code from a crafted checkpoint even "
                "with weights_only=True"
            ),
            "installed_version": torch_version,
            "environment_status": _mitigation_status(torch_version, (2, 6)),
            "mitigation": "evaluation venv pins torch 2.13 (>= 2.6 fixed range)",
        },
        {
            "id": "CVE-2025-6921",
            "component": "transformers",
            "summary": "transformers advisory remediated in the 4.53 release line",
            "installed_version": transformers_version,
            "environment_status": _mitigation_status(
                transformers_version, (4, 53)
            ),
            "mitigation": "upgrade to transformers>=4.53",
        },
        {
            "id": None,
            "component": "spacy-llm",
            "summary": (
                "spacy-llm is not part of the evaluation dependency set; its "
                "advisory surface does not apply to this environment"
            ),
            "installed_version": spacy_llm_version,
            "environment_status": (
                "not-installed" if spacy_llm_version is None else "review_required"
            ),
            "mitigation": "keep spacy-llm uninstalled",
        },
    ]


def _build_vulnerability_report() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_by": "runtime/redaction_evaluation/inventory.py",
        "tool": "pip-audit",
        "note": (
            "pip-audit queries a remote advisory database; when the "
            "environment is offline the audit is recorded as unavailable "
            "without failing the inventory build"
        ),
        "audit": _run_pip_audit(),
        "known_advisories": _known_advisories(),
    }


def build_inventory(
    candidate_ids: list[str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build (dependency_report, license_report, vulnerability_report).

    Raises ``KeyError`` for candidate ids missing from the pinned
    candidate-to-top-level-packages map. All three documents are
    JSON-serializable with deterministic (name-sorted) ordering.
    """

    for candidate_id in candidate_ids:
        if candidate_id not in CANDIDATE_TOP_LEVEL_PACKAGES:
            raise KeyError(candidate_id)
    dists = _installed_distributions()
    closures = {
        candidate_id: _dependency_closure(
            CANDIDATE_TOP_LEVEL_PACKAGES[candidate_id], dists
        )
        for candidate_id in candidate_ids
    }
    dependency_report = _build_dependency_report(candidate_ids, dists, closures)
    license_report = _build_license_report(candidate_ids, dists, closures)
    vulnerability_report = _build_vulnerability_report()
    return dependency_report, license_report, vulnerability_report
