# EM-Safe Mods

Mods are advisory post-processors over adapter emissions. They can annotate evidence and suggest review routing, but they cannot write canonical decisions, approve signoff, resolve compliance, or create direct blocking results.

## Table of Contents

- [Scope](#scope)
- [Mod Matrix](#mod-matrix)
- [Safety Contract](#safety-contract)
- [Manifest Expectations](#manifest-expectations)
- [Development](#development)
- [Related Documentation](#related-documentation)

## Scope

This directory contains declarative mod packages. A mod may inspect adapter emissions and emit advisory outputs such as routing hints, dependency signals, source evidence annotations, and advisory governance results.

Mods must stay EM-safe: they are evidence and recommendation surfaces, not authority surfaces.

## Mod Matrix

| Mod | Purpose | Manifest |
| --- | --- | --- |
| [Dependency Risk](dependency_risk/README.md) | Flags dependency upgrade, pinning, SDK drift, and compatibility risk signals. | [`dependency_risk/manifest.yaml`](dependency_risk/manifest.yaml) |
| [Noisy Source Gate](noisy_source_gate/README.md) | Suggests manual gates for high-noise sources unless source trust is explicitly configured higher. | [`noisy_source_gate/manifest.yaml`](noisy_source_gate/manifest.yaml) |
| [Security Mentions](security_mentions/README.md) | Flags auth, token, secret, PII, webhook verification, and transport-exposure mentions. | [`security_mentions/manifest.yaml`](security_mentions/manifest.yaml) |

## Safety Contract

Allowed outputs:

- `dependency_signal`
- `routing_hint`
- `source_evidence_annotation`
- `advisory_governance_result`

Forbidden actions:

- `write_canonical_decision`
- `approve_signoff`
- `resolve_compliance`
- `create_blocking_ci_result`

Mods also must not bypass adapter validation, collapse confidence into an opaque score, or convert advisory findings into direct CI authority.

## Manifest Expectations

Each mod manifest must include:

- Stable `id`.
- Semver-like `version`.
- Human-readable `name`.
- Explicit `outputs`.
- Explicit `forbidden_actions`.

Any new output type or authority change requires documentation, tests or fixture validation, and an architecture decision when it changes the safety model.

## Development

Review manifests directly:

```bash
python - <<'PY'
from pathlib import Path
for path in sorted(Path("mods").glob("*/manifest.yaml")):
    print(path)
PY
```

Run the full repository gate before opening a PR:

```bash
ruff check adapter connectors
mypy adapter connectors
pytest adapter/core/tests connectors -q
```

## Related Documentation

- [Repository README](../README.md)
- [Adapter Core](../adapter/core/README.md)
- [ADR-0002 EM-Safe Mod Manifest](../docs/adr/0002-em-safe-mod-manifest.md)
- [ADR-0007 EM-Safe Mod Boundary](../docs/adr/0007-em-safe-mod-boundary.md)
