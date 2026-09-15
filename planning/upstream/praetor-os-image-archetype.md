# Upstream request: `os-image` archetype and flavor detection for OS image forges

Target: `cordanallm/praetor` (main, `89c56ec3`). Requested by `cordanaLLM/imago` (the image forge named in the Aegis-OS connected stack contract; today `lusoris/lusoris-cloud-images`) on 2026-09-15.

## Problem

No archetype in `.config/archetypes/` describes an OS image forge: a repository whose product is a bootable image built from Packer or mkosi definitions, shell provisioners, a declarative version manifest, Python verification suites, and a Go CLI/MCP server.

Adoption evidence on such a repository (praetor `89c56ec3`, `standardsctl adopt --dry-run`):

- Archetype auto-detection selects `framework` because `go.mod` and `cmd/` exist (the same heuristic reported in #36).
- `standardsctl flavor audit` selects `python-ml` because `pyproject.toml` and `tests/` exist, then demands `ruff.toml` and `uv`.
- With `--profile gitops-infra` the dry run succeeds but declares `kubeconform`, `checkov` and `tflint`, none of which apply; with `--profile container-image` it declares `hadolint`, `dockle` and `grype` and lowers the function bound to 50 lines, below the repository's enforced Power-of-10 limit of 60.

## Proposal

1. Add `.config/archetypes/os-image.yaml` (draft below, also tracked at `planning/archetypes/os-image.yaml` in the requesting repository).
2. Add a flavor detection rule that fires on `packer/*.pkr.hcl`, `mkosi.conf` or `build/mkosi.conf`, and treats `go.mod` + `cmd/` in such a repository as tooling, not a service.
3. Prefer the declared profile in `.standards.yaml` over heuristics (as proposed in #36).

```yaml
id: "os-image"
name: "OS Image Forge"
description: "Hardened, reproducible OS image pipelines (Packer/QEMU, mkosi, UKI) with declarative version manifests, shell provisioners under Power-of-10 bounds, and signed image artifacts"
runtime: "image"

complexity:
  max_cyclomatic: 10
  max_cognitive: 12
  max_func_loc: 60
  max_statements: 40

branch_protection:
  enforce_linear_history: true
  require_signed_commits: true
  required_approving_reviewers: 1
  dismiss_stale_reviews: true

supply_chain:
  slsa_level: 3
  enforce_cosign: true
  require_sbom: true

linters:
  - "packer"
  - "shellcheck"
  - "shfmt"
  - "yamllint"
  - "trivy"
  - "gitleaks"
  - "codespell"

devcontainer_features:
  - "ghcr.io/devcontainers/features/common-utils:2"
  - "ghcr.io/devcontainers/features/go:1"
  - "ghcr.io/devcontainers/features/python:1"
```

## Interim

`cordanaLLM/imago` adopts with `gitops-infra` (60-line bound, yamllint and trivy already enforced) and switches to `os-image` once it ships; the switch is a tracked step in its planning graph.
