# SPDX-License-Identifier: MIT
"""Loader for the candidate-neutral redaction evaluation corpus.

Stdlib-only on purpose: this module is imported by both the contract tests and
the runtime evaluation harness, so it must not pull optional dependencies.

Committed corpus files never contain secret-shaped raw tokens. Any string
value that would trip the repository secret scan is committed as an
obfuscation marker object ``{"__b64rev__": "<base64 of the reversed
string>"}``. :func:`deobfuscate` restores the original text. Expected span
offsets always index the de-obfuscated text.

Two ``eval_directives`` forms interact with loading:

- ``obfuscated_object``: an entire object (used when a *key* is sensitive) is
  committed as the base64 of the reversed canonical JSON of that object.
  :func:`load_input_record` decodes it and installs it at the directive path
  inside the observation.
- ``binary_field``: left untouched by the loader; the evaluation harness is
  responsible for converting the referenced base64 payload to ``bytes``
  before invoking sanitization.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

_B64REV_KEY = "__b64rev__"

_PATH_TOKEN_RE = re.compile(r"^([A-Za-z0-9_$-]+)((?:\[[0-9]+\])*)$")
_PATH_INDEX_RE = re.compile(r"\[([0-9]+)\]")


def _decode_b64rev(encoded: str) -> str:
    """Decode one obfuscation payload: base64 -> UTF-8 -> reversed text."""
    return base64.b64decode(encoded.encode("ascii")).decode("utf-8")[::-1]


def deobfuscate(value: object) -> object:
    """Recursively replace ``__b64rev__`` marker objects with their plain text.

    Any other value passes through structurally unchanged. Dicts and lists are
    rebuilt so the caller receives a fully de-obfuscated copy.
    """
    if isinstance(value, dict):
        if set(value.keys()) == {_B64REV_KEY} and isinstance(value[_B64REV_KEY], str):
            return _decode_b64rev(value[_B64REV_KEY])
        return {key: deobfuscate(sub) for key, sub in value.items()}
    if isinstance(value, list):
        return [deobfuscate(item) for item in value]
    return value


def resolve_field_path(observation: dict[str, Any], field_path: str) -> object:
    """Resolve a dot-joined field path (with ``[n]`` list indexes) to a value.

    Example paths: ``excerpt``, ``source_ref.source_id``,
    ``metadata.webhook.issue.body``, ``metadata.comments[0].body``.

    Raises ``KeyError`` for a malformed token or missing key and
    ``IndexError`` for an out-of-range list index.
    """
    node: object = observation
    for token in field_path.split("."):
        match = _PATH_TOKEN_RE.match(token)
        if match is None:
            raise KeyError(f"malformed field path token: {token!r}")
        if not isinstance(node, dict):
            raise KeyError(f"cannot descend into non-object at {token!r}")
        node = node[match.group(1)]
        for index_text in _PATH_INDEX_RE.findall(match.group(2)):
            if not isinstance(node, list):
                raise KeyError(f"cannot index non-list at {token!r}")
            node = node[int(index_text)]
    return node


def _install_at_path(observation: dict[str, Any], field_path: str, value: object) -> None:
    """Install ``value`` at ``field_path`` inside the observation."""
    if "." in field_path:
        parent_path, _, leaf = field_path.rpartition(".")
        parent = resolve_field_path(observation, parent_path)
    else:
        parent, leaf = observation, field_path
    if not isinstance(parent, dict):
        raise KeyError(f"cannot install at non-object parent: {field_path!r}")
    parent[leaf] = value


def load_input_record(path: str | Path) -> dict[str, Any]:
    """Parse one committed input record and return its de-obfuscated form.

    Applies ``__b64rev__`` unwrapping recursively, then expands an
    ``obfuscated_object`` directive (if present) into the observation. The
    returned dict is what the evaluation harness should feed to a candidate.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    record = deobfuscate(raw)
    if not isinstance(record, dict):
        raise ValueError(f"input record is not an object: {path}")
    directives = record.get("eval_directives")
    if isinstance(directives, dict):
        obfuscated = directives.get("obfuscated_object")
        if isinstance(obfuscated, dict):
            decoded = json.loads(_decode_b64rev(obfuscated["b64rev"]))
            observation = record["observation"]
            if not isinstance(observation, dict):
                raise ValueError(f"observation is not an object: {path}")
            _install_at_path(observation, obfuscated["path"], decoded)
    return record


def iter_manifest(manifest_path: str | Path) -> Iterator[dict[str, Any]]:
    """Yield manifest record entries in committed (record_id-sorted) order."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    records = manifest["records"]
    if not isinstance(records, list):
        raise ValueError(f"manifest records is not a list: {manifest_path}")
    for entry in records:
        if not isinstance(entry, dict):
            raise ValueError(f"manifest entry is not an object: {manifest_path}")
        yield entry
