# SPDX-License-Identifier: MIT
"""Single source of truth for the product release channel.

The whole **Bicameral Integrations** product is in **Beta** — even though individual connectors
are flip-ready and mods are built, the overall product has not reached GA. Each connector and mod
descriptor carries its own per-component semver ``version`` (which may diverge post-beta) PLUS a
uniform ``channel`` field. Both ``scripts/validate_connector_config.py`` and
``scripts/validate_mod_config.py`` enforce that every descriptor's ``channel`` equals
``PRODUCT_CHANNEL`` here — so the Beta state is uniform + single-sourced. **To cut GA: flip this to
``"ga"`` and re-stamp every descriptor (the validator will fail until they agree).**

Per-component ``version`` is intentionally NOT pinned to one value (the operator chose per-component
semver so a connector/mod can bump independently as its emission/contract shape changes); only the
``channel`` is uniform.
"""

from __future__ import annotations

#: The uniform product release channel every descriptor must declare. Allowed: "beta" | "ga".
PRODUCT_CHANNEL = "beta"

#: The baseline per-component version (new descriptors start here; bumps are per-component).
VERSION_BASELINE = "0.1.0"
