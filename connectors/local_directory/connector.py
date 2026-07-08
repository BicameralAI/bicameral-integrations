# SPDX-License-Identifier: MIT
"""Local-directory connector: dropped files into neutral Observations.

A file captured from a watched local directory — represented as a
``{path, content, modified}`` payload — maps to one provider-neutral
Observation. Port of the parse shape from `bicameral-mcp`
`events/sources/local_directory.py`, reduced to the neutral surface; the live
directory scan, watermark two-phase commit, size caps, and extension filtering
stay in the operator runtime (see ``auth.md``).
"""

from __future__ import annotations

import hashlib
from pathlib import PurePosixPath

from adapter.core.capabilities import SourceCapabilities, SourceMode
from adapter.core.emissions import SourceRef
from adapter.core.observations import Observation
from adapter.core.redaction import redact

_DEFAULT_KIND = "planning"


def _path_token(path: str) -> str:
    """Stable opaque token derived from the file path.

    Sha256 first 16 chars — deterministic (re-ingesting the same path yields the
    same ref) without embedding the operator's filesystem layout in the ref.
    """
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]


def parse_file(payload: dict) -> Observation:
    """Map a ``{path, content, modified}`` file payload into an Observation.

    File content + the filename stem are operator-supplied free text -> **redact-and-pass**
    (secret/PHI/PAN + email/phone scrubbed; SG-2026-06-13-A: a local/passive source still
    needs redaction parity — no network boundary is not no PII boundary, and FX-SEC-001
    only backstops secret/PHI/PAN). The excerpt is the redacted content, falling back to the
    redacted stem then the opaque path token so the non-empty-excerpt rule always holds. The
    sha256 path token (the ``ref``) is an opaque floor and is NOT redacted.
    """
    path = str(payload.get("path") or "")
    content = redact(str(payload.get("content") or ""))
    token = _path_token(path)
    stem = redact(PurePosixPath(path).stem) or token
    # source_type_label is a freeform operator-supplied label -> redact-and-pass too
    # (purple-team #170 / SG-2026-06-13-C; the platform screen now backstops kind fleet-wide).
    kind = redact(str(payload.get("source_type_label") or _DEFAULT_KIND)) or _DEFAULT_KIND
    return Observation(
        source_ref=SourceRef(source_id="local_directory", ref=f"local-{token}", kind=kind),
        excerpt=content or stem,
        mode=SourceMode.PASSIVE,
        title=stem,
        timestamp=str(payload.get("modified") or ""),
    )


class LocalDirectoryConnector:
    """Local-directory connector identity plus the file parse surface.

    Declares the passive polling mode; the live directory scan, watermark
    two-phase commit, size caps, and extension filtering are deferred to the
    operator runtime.
    """

    source_id = "local_directory"
    capabilities = SourceCapabilities(modes=frozenset({SourceMode.PASSIVE}))

    def observations(self, payload: dict) -> list[Observation]:
        if not isinstance(payload, dict):  # untrusted poll boundary: skip, don't crash (#59)
            return []
        return [parse_file(payload)]
