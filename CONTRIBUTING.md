# Contributing to lusoris-cloud-images

Thank you for your interest in contributing to `lusoris-cloud-images`! We welcome contributions ranging from new hardware acceleration stacks and hypervisor targets to security hardening and bug fixes.

---

## Development & PR Workflow

This project follows **Trunk-Based Development** with protected `main` branch. Direct commits to `main` are rejected.

### Step-by-Step Flow

1. **Create a topic branch** off `main`:

   ```bash
   git checkout -b feat/my-new-flavor
   ```

2. **Make your changes**:
   - Component versions **must** be defined in [`versions.json`](versions.json), never hardcoded in shell scripts.
   - Shell provisioners must adhere to NASA/JPL Power of 10 rules:
     - Enforce `set -euo pipefail`.
     - Functions strictly <= 60 lines.
     - Checked exit statuses and bounded control loops.
     - ShellCheck passes with zero warnings.
   - **Privacy invariant**: Zero private subnets (`10.x`, `192.168.x`) or local home paths.
3. **Run local verification gates**:

   ```bash
   make fmt-check
   make lint
   make test         # or make test-all for benchmarks and full coverage
   pre-commit run --all-files
   ```

4. **Commit with Conventional Commits**:

   ```bash
   git commit -m "feat(docker): add compose plugin and tuned log rotation"
   ```

   Allowed types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`.
5. **Push and create a Pull Request**:

   ```bash
   git push -u origin feat/my-new-flavor
   gh pr create --fill
   ```

6. **CI Gate**:
   All checks in `.github/workflows/ci.yml` and `.github/workflows/security-scans.yml` must pass. The branch protection gate requires `required-checks` from `.github/workflows/required-aggregator.yml`.

---

## Documentation Synchrony

Any user-discoverable addition (new flavor, Packer variable, or provisioner step) **must be reflected in documentation** in the exact same commit:

- Update [`README.md`](README.md) and relevant guides in [`docs/`](docs/).

## Developer Certificate of Origin (DCO)

By contributing to this repository, you certify that you have the right to submit the code under the project's Apache 2.0 license.
