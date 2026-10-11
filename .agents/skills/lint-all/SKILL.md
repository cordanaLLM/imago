---
name: lint-all
description: Run Packer formatting, Packer validate, ShellCheck, Actionlint, Yamllint, Codespell and Ruff across the entire repository
---

# /lint-all

Runs all static analysis and linting quality gates.

## Usage

```bash
make lint
```

`make lint` ends with `ruff check .` + `ruff format --check .`, every Python file.
Pinned Ruff version: `.github/requirements/lint.txt`. Rule set + dated exemptions for
`praetorctl adopt` files: `ruff.toml`.
