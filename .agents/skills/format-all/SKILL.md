---
name: format-all
description: Format all Packer templates, shell provisioners, YAML, and configuration files across the repository.
---

# Format All Skill

Run repository-wide formatters to ensure zero style drift across shell, Packer HCL, YAML, and Python files.

## Commands

```bash
# 1. Format Packer HCL configurations
cd packer && packer fmt . && cd ..

# 2. Format shell provisioner scripts
shfmt -w -i 2 -ci packer/provisioners/*.sh

# 3. Check / autofix codespell findings
codespell -w

# 4. Verify Yamllint passes cleanly
yamllint -c .yamllint.yml .github/ packer/http/

# 5. Apply safe Ruff fixes, then format Python files
ruff check --fix .
ruff format .
```

## Invariants
- `shfmt` uses 2 spaces indentation (`-i 2`) and switch-case indentation (`-ci`).
- Never introduce trailing whitespace or empty lines at shell script end.
- `ruff format` skips files under `[format] exclude` in `ruff.toml`: written by `praetorctl adopt`, never hand-edited.
