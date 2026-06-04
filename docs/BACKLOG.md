# Project Backlog

## Blockers (Must Fix Before Progress)

### Security Blockers

<!-- Format: - [ ] [S#] Description -->

### Development Blockers

<!-- Format: - [ ] [D#] Description -->

## Backlog (Planned Work)

<!-- Format: - [ ] [B#] Description -->
- [ ] [B1] SHA-pin the legacy workflows `.github/workflows/ci.yml` (`actions/checkout@v4`, `setup-python@v5`) and `secret-scan.yml` (`actions/checkout@v4`, `trufflehog@main` → pinned SHA) to match the gate workflows' supply-chain hygiene (devil's-advocate P1, ci-gates cycle).
- [ ] [B2] Backfill SPDX license headers across all `.py` files, then flip the `license-headers` gate from advisory to blocking.
- [ ] [B3] Ecosystem governance rollout: port the governance-integrity gate + compliance mappings to `bicameral-bot`/`bicameral-mcp`/`bicameral-cloud`; evaluate AGT as a `bicameral-bot` sidecar (operator request, 2026-06-04).

## Wishlist (Nice to Have)

<!-- Format: - [ ] [W#] Description -->

---
_Updated by /qor-* commands automatically_
