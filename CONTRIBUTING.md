# Contributing to Bicameral Integrations

Thank you for considering a contribution to Bicameral Integrations. This repo
contains source adapters and EM-safe mods that emit protocol-shaped objects into
the Bicameral gateway without owning canonical state.

## How to Contribute

1. Fork the repository.
2. Create a branch for your change.
3. Keep adapter and mod behavior aligned with the authority boundaries in
   `README.md` and `docs/adr/`.
4. Add or update tests when behavior changes.
5. Run the relevant test command before opening a pull request.
6. Open a pull request using the repository template.

## Local Checks

```bash
pytest -v tests/
pre-commit run --all-files
```

## Issue Reports

Use the issue templates for bugs, feature requests, and documentation problems.
Include source evidence, expected behavior, and any relevant protocol contracts.

## License

By contributing, you agree that your contributions will be licensed under the MIT
license.
