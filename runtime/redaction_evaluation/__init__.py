# SPDX-License-Identifier: MIT
"""Spike-only comparative evaluation of replaceable redaction detector backends.

Everything in this package exists to produce the ADR-0020 decision evidence
(issues #277-#280). Nothing here is a production dependency: candidate
packages (Presidio, GLiNER, DataFog) are imported lazily and only inside the
evaluation venv. The Bicameral wrapper in ``adapter.core.redaction_receipt``
remains the authoritative boundary; a backend owns detection only.
"""
