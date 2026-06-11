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

## Pull Request Titles

CI (`pr-hygiene / conventional-title`) requires every PR title to match
[Conventional Commits](https://www.conventionalcommits.org/). The check is a hard
gate — a non-conforming title fails the PR. The exact pattern enforced is:

```
^(feat|fix|docs|chore|refactor|test|ci|build|perf|style|revert)(\([\w./-]+\))?!?: .+
```

- **Allowed types** (the only ones that pass): `feat`, `fix`, `docs`, `chore`,
  `refactor`, `test`, `ci`, `build`, `perf`, `style`, `revert`. Anything else
  (e.g. `research:`, `seal:`) is rejected.
- **Scope** is optional and, when present, may contain only word characters,
  `.`, `/`, and `-`. **A comma or a space inside the scope fails the check** —
  `fix(fathom,claude_code):` and `fix(a b):` are both rejected.
  - To cover several connectors in one title, use a single parent scope
    (`fix(connectors): ...`) or drop the scope (`fix: ...`).
- A `!` before the colon (`feat(api)!: ...`) marks a breaking change and passes.

Examples that pass: `feat(fathom): add webhook verify`, `fix: floor non-dict
payload`, `docs(connectors): mark Linear flip-ready`.

## Bring your own tools — the sibling registry

You are **not** required to adopt the maintainer's process tooling. The only thing your
PR must satisfy is the shared **bic-logic** contract plus a clean working tree. Everything
you run *locally* — a governance system, an AI assistant, an IDE plugin, or a homegrown
framework — is welcome as a **registered sibling**: leak-guarded, never tracked, never
referenced.

To use your own tool: add a row to [`docs/governance/SIBLINGS.md`](docs/governance/SIBLINGS.md),
add its scratch root to `.gitignore`, and keep its artifacts out of tracked files. See the
registry for the full rules.

## Issue Reports

Use the issue templates for bugs, feature requests, and documentation problems.
Include source evidence, expected behavior, and any relevant protocol contracts.

## License

By contributing, you agree that your contributions will be licensed under the MIT
license.
