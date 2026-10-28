# Contributing to imago

Thank you for your interest in contributing to `imago`! We welcome contributions ranging from new hardware acceleration stacks and hypervisor targets to security hardening and bug fixes.

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
   make verify-all
   ```

   `make lint` ends with `ruff check .` and `ruff format --check .` over every Python file; `ruff.toml` holds the rule set. Install the pinned Ruff with `pip install --require-hashes -r .github/requirements/lint.txt`. `ruff check --fix .` applies the safe fixes and `ruff format .` formats. The files that `praetorctl adopt` writes are exempt by name in `ruff.toml`, each line with the engine issue and an end date; `tests/test_python_lint_gate.py` fails when an exemption has passed its date or is no longer needed. Do not add an own file to those lists; fix the finding.

   `make test` runs the seed corpus of every Go fuzz target (`FuzzParse` and `FuzzParseResult` in `pkg/aegis`, `FuzzParseRequirement` and `FuzzParseArtifactManifest` in `pkg/kernel`) as ordinary cases. After a change to one of these parsers, also run `make fuzz`: it fuzzes each target in turn for `FUZZTIME` (default `30s`, for example `make fuzz FUZZTIME=5m`). When a run fails, Go writes the failing input to `testdata/fuzz/<target>/` in the package; commit that file with the fix so the input stays a regression case.

   The Git hooks and `make verify-all` run the Praetor engine at the commit that `PRAETOR_REF` names in `.github/workflows/ci.yml`, not the `praetorctl` on your `PATH`. The launcher `.config/lefthook/engine.sh` installs that commit with `go install` on first use, into `${XDG_CACHE_HOME:-$HOME/.cache}/praetor/engine/<commit>`, and fails with the command to run when it cannot. To run the same engine by hand, call `sh .config/lefthook/engine.sh audit`; `make praetor-engine-path` prints the binary in use.
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
   `required-checks` accepts no skipped check (ADR-0027). Every job a pull request starts begins with the `Stop on a draft pull request` step, carries no job `if:` and no `needs`, and its workflow lists `ready_for_review` in its `pull_request` types: on a draft every gate fails with a notice, and marking the pull request ready reruns them. A job that tests only some paths runs `dorny/paths-filter` on `.github/path-filters.yml` and gates its later steps on the filter named after the job id; when no tested path changed it passes without doing the work. `tests/test_required_aggregator.py` and `tests/test_path_filters.py` hold every job to this shape.
   The rule set in `.github/rulesets/main.json` requires each of these jobs by name. A new or renamed job changes that list in the same pull request; `praetorctl audit` fails until it matches the workflows. Job names carry no toolchain version, so a version bump never renames a required check.

   The live tests need Docker and bash. On a host without them, or when a preparation step runs past its bound, they skip. The pytest job of `ci.yml` sets `IMAGO_REQUIRE_LIVE_TESTS=1`, and there the same condition fails the test (`tests/harness/live.py`). Set the variable locally to check that every live test runs.

---

## Documentation Synchrony

Any user-discoverable addition (new flavor, Packer variable, or provisioner step) **must be reflected in documentation** in the exact same commit:

- Update [`README.md`](README.md) and relevant guides in [`docs/`](docs/).

## Developer Certificate of Origin (DCO)

By contributing to this repository, you certify that you have the right to submit the code under the project's licence, the European Union Public Licence 1.2 (`EUPL-1.2`).

## Licence Information (REUSE)

Every file carries licence and copyright information that `reuse lint` can read. [`REUSE.toml`](REUSE.toml) assigns `EUPL-1.2` to the whole tree, so a new file of your own needs nothing more than the `Copyright 2026 Lusoris` header.

A file you take from another project keeps its licence:

1. Add the licence text with `reuse download <SPDX identifier>`.
2. Add an `[[annotations]]` table for the file **after** the whole-tree table in `REUSE.toml`. REUSE applies only the last table that matches a file.
3. Run `reuse lint`. The pre-commit hook and the `REUSE lint` check run the same command.
