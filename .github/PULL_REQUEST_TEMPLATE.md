<!-- markdownlint-disable MD041 -- fragment rendered under the pull request title -->
## Description
<!-- Provide a concise description of the changes introduced by this PR. -->

## Changes Checklist

- [ ] **Single Source of Truth**: All versions updated via `versions.json` (no hardcoded versions in shell scripts).
- [ ] **NASA/JPL Power of 10**: All shell script functions are <= 60 lines and enforce `set -euo pipefail`.
- [ ] **ShellCheck & Linters**: `make lint` passes locally with zero warnings.
- [ ] **Automated Tests**: `make test` passes (`pytest tests/ -v`).
- [ ] **Pre-commit**: `pre-commit run --all-files` passes clean.
- [ ] **Privacy Invariant**: Verified zero occurrences of private IP ranges (`10.x`, `192.168.x`) or local filesystem paths.
- [ ] **Docs & Code Synchrony**: Documentation updated (`README.md`, `ONBOARDING.md`, `docs/`) in the exact same commit.

## Related Issues / Epics

Fixes #
Ref #
