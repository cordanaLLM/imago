---
name: regen-docs
description: Build and validate the Material for MkDocs documentation portal in strict mode.
---

# Regenerate Documentation Portal

Documentation portal uses Material for MkDocs and is deployed to GitHub Pages.

## Build in Strict Mode
```bash
# Install the hash-locked dependencies the workflows install
pip install --require-hashes -r .github/requirements/docs.txt

# Build site with zero tolerance for broken links or warnings
mkdocs build --strict
```

## Serve Locally for Preview
```bash
mkdocs serve
```

## Invariants
- All markdown links within `docs/` must resolve to existing files.
- Links to external repository files (`versions.json`, root governance) must use full GitHub repository URLs to avoid MkDocs out-of-tree warnings.
- Keep `mkdocs.yml` navigation structure aligned with all new topics.
